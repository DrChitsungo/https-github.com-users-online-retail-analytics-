"""Controlled failing fixture: prove that a critical validation failure PREVENTS publication.

Takes the staged tables of a completed run, injects four deliberate faults into COPIES held in memory,
re-runs the real validation suites and the real publish() gate, and records the outcome.
Usage: PYTHONPATH=src python scripts/demo_gate_failure.py <run_id> reports/evidence/gate_failure_demo.json
Requires CUSTOMER_KEY_SECRET only if you also want the full flow; this script does not use it.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from retail_pipeline import config, publish, validation

run_id, out = sys.argv[1], Path(sys.argv[2])
cfg = config.load_config()
root = config.ROOT
rd = root / "data" / "runs" / run_id
tables = {p.stem: pd.read_parquet(p) for p in (rd / "staging").glob("*.parquet")}
silver = rd / "silver"
disp = pd.read_parquet(silver / "row_disposition.parquet", columns=["raw_row_id", "disposition", "reason_code", "line_revenue_raw"])
ing = json.loads((root / "reports" / "runs" / run_id / "ingestion_manifest.json").read_text())
clean = json.loads((root / "reports" / "runs" / run_id / "cleaning_summary.json").read_text())
file_rows = {k: len(pd.read_parquet(silver / f"{k}.parquet", columns=["raw_row_id"])) for k in ("quarantine", "excluded")}


def evaluate(t):
    recon = validation.build_reconciliation(cfg, raw_rows=ing["rows"], raw_revenue_independent=ing["raw_revenue_control_total"], disposition=disp,
                                            file_rows=file_rows, tables=t, overlap_evidence=clean["overlap_evidence"])
    return validation.validate_outputs(cfg, t, recon)


baseline = evaluate(tables)
fact = tables["fact_sales_line"]
legit_returns = int((fact["is_cancellation"] & (fact["quantity"] < 0)).sum())

bad = {k: v.copy() for k, v in tables.items()}
f = bad["fact_sales_line"]
f.loc[1, "line_id"] = f.loc[0, "line_id"]                    # fault 1: duplicate primary key
f.loc[2, "unit_price"] = -5.0                                  # fault 2: negative price survived cleaning
f.loc[3, "customer_key"] = "12345"                             # fault 3: raw-looking identifier instead of keyed pseudonym
f.loc[4, "line_revenue"] = f.loc[4, "line_revenue"] + 1000.0   # fault 4: revenue no longer reconciles
faulty = evaluate(bad)

failed = [{"suite": s["suite"], "expectation": i["expectation"], "column": i["column"], "unexpected_count": i["result"].get("unexpected_count")}
          for s in faulty["suites"] for i in s["results"] if not i["success"] and i["severity"] == "critical"]
recon_failed = [r["check"] for r in faulty["reconciliation"] if not r["within_tolerance"]]

pub_root = root / "data" / "published"
latest_before = (pub_root / "LATEST.json").read_text() if (pub_root / "LATEST.json").exists() else None
ctx = config.new_run(cfg, run_id="gate-demo-blocked")
priv_ok = {"published_pii_hits": 0}
blocked, message = False, ""
try:
    publish.publish(ctx, cfg, {k: rd / "staging" / f"{k}.parquet" for k in tables}, faulty, {"publish_allowed": True, "critical_failures": 0}, priv_ok, ing, "demo")
except publish.PublicationBlocked as exc:
    blocked, message = True, str(exc)
latest_after = (pub_root / "LATEST.json").read_text() if (pub_root / "LATEST.json").exists() else None

evidence = {
    "run_id_used_as_input": run_id,
    "baseline_critical_failures": baseline["critical_failures"], "baseline_expectations": baseline["expectations_evaluated"],
    "legitimate_cancellation_lines_in_baseline_that_passed": legit_returns,
    "injected_faults": ["duplicate line_id", "negative unit_price on a retained line", "raw-looking customer_key '12345'", "line_revenue altered by +1000"],
    "faulty_critical_failures": faulty["critical_failures"], "faulty_publish_allowed": faulty["publish_allowed"],
    "failed_critical_expectations": failed, "failed_reconciliation_checks": recon_failed,
    "publish_raised_PublicationBlocked": blocked, "publish_message": message,
    "published_directory_created": (pub_root / "gate-demo-blocked").exists(),
    "latest_pointer_unchanged": latest_before == latest_after,
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, indent=2, sort_keys=True))
print(json.dumps({k: evidence[k] for k in ("baseline_critical_failures", "faulty_critical_failures", "publish_raised_PublicationBlocked", "published_directory_created", "latest_pointer_unchanged")}, indent=2))
assert blocked and not evidence["published_directory_created"] and evidence["latest_pointer_unchanged"] and baseline["critical_failures"] == 0 and faulty["critical_failures"] > 0
