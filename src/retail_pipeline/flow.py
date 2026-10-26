"""Prefect orchestration: Sources -> ingestion -> cleaning -> transformation -> integration -> validation -> publication.

DAG (arrows = dependencies; tasks on the same level may run concurrently)

    ingest ──┬─> profile_source
             └─> validate_bronze ──> clean ──> transform ──> integrate ──┬─> validate_outputs ─┐
                                                                         ├─> bias_detection    ├─> publish ──> evidence_summary
                                                                         └─> privacy_scan  ────┘

Design choices
  * Tasks exchange file paths and small dicts, never data frames or secrets, so nothing sensitive is persisted
    in Prefect's metadata. The pseudonymisation secret is read from the environment inside tasks that need it.
  * Gate failures are deterministic, so only I/O-bound `ingest` retries; `publish` never retries a blocked gate.
  * On any failure the flow writes run_status.json (FAILED + error class) and an audit event, and nothing is
    published (publication is the last step and is atomic).
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from .config import ROOT

os.environ.setdefault("PREFECT_HOME", str(ROOT / ".prefect"))
os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "INFO")

import json  # noqa: E402

import pandas as pd  # noqa: E402
from prefect import flow, get_run_logger, task  # noqa: E402

from . import __version__, bias, config, ingest, integrate, privacy, profiling, publish, transform, validation  # noqa: E402
from .audit import AuditLogger  # noqa: E402

_AUDITS: dict[str, AuditLogger] = {}


def _logger():
    """Prefect run logger inside a flow/task run, plain logger otherwise (keeps tasks unit-testable)."""
    try:
        return get_run_logger()
    except Exception:  # MissingContextError outside a run
        import logging
        return logging.getLogger("retail_pipeline")


def audit_for(ctx: config.RunContext) -> AuditLogger:
    return _AUDITS[ctx.run_id]


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))


# ------------------------------------------------------------------------------------------------ tasks
@task(name="ingest", retries=2, retry_delay_seconds=2)
def t_ingest(cfg: dict, ctx: config.RunContext) -> dict:
    a, log = audit_for(ctx), _logger()
    with a.span("READ", "raw/online_retail_II.csv", task="ingest") as s:
        m = ingest.ingest(cfg, ctx)
        s["rows_out"] = m["rows"]
        s["extra"]["sha256_prefix"] = m["source_sha256"][:12]
    a.event("WRITE", "bronze/raw_strings", task="ingest", rows_in=m["rows"], rows_out=m["rows"])
    log.info("ingested %s rows; checksum matches pin: %s", m["rows"], m["checksum_matches_pin"])
    return m


@task(name="profile_source")
def t_profile(cfg: dict, ctx: config.RunContext, m: dict) -> dict:
    a = audit_for(ctx)
    with a.span("READ", "raw/online_retail_II.csv", task="profile_source", rows_in=m["rows"]) as s:
        prof = profiling.main(str(ctx.root / cfg["source"]["file"]), str(ctx.report_dir / "source_profile.json"))
        s["rows_out"] = prof["rows"]
    a.event("WRITE", "reports/source_profile.json", task="profile_source")
    return {"rows": prof["rows"], "path": "source_profile.json"}


@task(name="validate_bronze")
def t_validate_bronze(cfg: dict, ctx: config.RunContext, m: dict) -> dict:
    a = audit_for(ctx)
    bronze = pd.read_parquet(ctx.root / m["bronze_path"])
    with a.span("VALIDATE", "bronze/raw_strings", task="validate_bronze", rows_in=len(bronze)) as s:
        res = validation.validate_bronze(cfg, bronze)
        s["rows_out"] = len(bronze)
        s["extra"].update(critical_failures=res["critical_failures"], warning_failures=res["warning_failures"])
    _write_json(ctx.report_dir / "validation_bronze.json", res)
    return res


@task(name="clean")
def t_clean(cfg: dict, ctx: config.RunContext, m: dict, bronze_validation: dict) -> dict:
    validation.assert_gate(bronze_validation, "bronze validation")
    a = audit_for(ctx)
    secret = privacy.load_secret(cfg)
    with a.span("TRANSFORM", "silver/cleaning+pseudonymisation", task="clean", rows_in=m["rows"], rules=ctx.rules_version) as s:
        summ = transform.build_silver(cfg, ctx, ctx.root / m["bronze_path"], secret)
        s["rows_out"] = summ["rows_retained"]
        s["extra"].update(quarantined=summ["rows_quarantined"], excluded=summ["rows_excluded"], key_id=privacy.key_id(secret))
    for part in ("retained", "quarantine", "excluded", "row_disposition"):
        n = summ["rows_retained"] if part == "retained" else summ["rows_quarantined"] if part == "quarantine" else summ["rows_excluded"] if part == "excluded" else summ["rows_raw"]
        a.event("WRITE", f"silver/{part}", task="clean", rows_out=n)
    summ["key_id"] = privacy.key_id(secret)
    return summ


@task(name="transform")
def t_transform(cfg: dict, ctx: config.RunContext, clean_summary: dict) -> str:
    a = audit_for(ctx)
    silver = Path(clean_summary["silver_dir"])
    with a.span("TRANSFORM", "silver/fact_sales_line", task="transform", rows_in=clean_summary["rows_retained"]) as s:
        fact = transform.build_fact(cfg, ctx, silver)
        path = silver / "fact_sales_line.parquet"
        fact.to_parquet(path, index=False)
        s["rows_out"] = len(fact)
    return str(path)


@task(name="integrate")
def t_integrate(cfg: dict, ctx: config.RunContext, fact_path: str, clean_summary: dict) -> dict:
    a = audit_for(ctx)
    fact = pd.read_parquet(fact_path)
    retained = pd.read_parquet(Path(clean_summary["silver_dir"]) / "retained.parquet", columns=["raw_row_id", "stock_code", "description"])
    stage = ctx.run_dir / "staging"
    stage.mkdir(parents=True, exist_ok=True)
    with a.span("TRANSFORM", "staging/integration", task="integrate", rows_in=len(fact)) as s:
        tables = integrate.integrate(fact, retained)
        s["rows_out"] = sum(len(t) for t in tables.values())
    paths = {}
    for name, df in tables.items():
        p = stage / f"{name}.parquet"
        df.to_parquet(p, index=False)
        paths[name] = str(p)
        a.event("WRITE", f"staging/{name}", task="integrate", rows_out=len(df))
    return paths


def _load(paths: dict) -> dict[str, pd.DataFrame]:
    return {k: pd.read_parquet(v) for k, v in paths.items()}


@task(name="validate_outputs")
def t_validate_outputs(cfg: dict, ctx: config.RunContext, m: dict, clean_summary: dict, staging: dict) -> dict:
    a = audit_for(ctx)
    silver = Path(clean_summary["silver_dir"])
    tables = _load(staging)
    disp = pd.read_parquet(silver / "row_disposition.parquet", columns=["raw_row_id", "disposition", "reason_code", "line_revenue_raw"])
    file_rows = {"quarantine": len(pd.read_parquet(silver / "quarantine.parquet", columns=["raw_row_id"])),
                 "excluded": len(pd.read_parquet(silver / "excluded.parquet", columns=["raw_row_id"]))}
    recon = validation.build_reconciliation(cfg, raw_rows=m["rows"], raw_revenue_independent=m["raw_revenue_control_total"], disposition=disp,
                                            file_rows=file_rows, tables=tables, overlap_evidence=clean_summary["overlap_evidence"])
    with a.span("VALIDATE", "staging/*", task="validate_outputs", rows_in=sum(len(t) for t in tables.values())) as s:
        res = validation.validate_outputs(cfg, tables, recon)
        s["rows_out"] = len(tables["fact_sales_line"])
        s["extra"].update(critical_failures=res["critical_failures"], warning_failures=res["warning_failures"])
    _write_json(ctx.report_dir / "validation_outputs.json", res)
    recon.to_csv(ctx.report_dir / "reconciliation.csv", index=False)
    return res


@task(name="bias_detection")
def t_bias(cfg: dict, ctx: config.RunContext, clean_summary: dict, staging: dict) -> dict:
    a = audit_for(ctx)
    disp = pd.read_parquet(Path(clean_summary["silver_dir"]) / "row_disposition.parquet")
    fact = pd.read_parquet(staging["fact_sales_line"])
    with a.span("TRANSFORM", "reports/bias_report", task="bias_detection", rows_in=len(fact)) as s:
        rep = bias.build_bias_report(cfg, disp, fact)
        s["rows_out"] = len(rep["country_representation"]["table"])
    _write_json(ctx.report_dir / "bias_report.json", rep)
    (ctx.report_dir / "bias_report.md").write_text(bias.to_markdown(rep))
    return {"findings": rep["findings"], "small_cell_countries": rep["country_representation"]["small_cell_countries"]}


@task(name="privacy_scan")
def t_privacy(cfg: dict, ctx: config.RunContext, m: dict, clean_summary: dict, staging: dict) -> dict:
    a = audit_for(ctx)
    silver = Path(clean_summary["silver_dir"])
    with a.span("TRANSFORM", "reports/privacy_scan", task="privacy_scan") as s:
        dim_p = pd.read_parquet(staging["dim_product"], columns=["description"])
        quar = pd.read_parquet(silver / "quarantine.parquet", columns=["description"])
        excl = pd.read_parquet(silver / "excluded.parquet", columns=["description"])
        scans = {"published.dim_product": privacy.pii_scan(dim_p, ["description"]),
                 "silver.quarantine": privacy.pii_scan(quar, ["description"]),
                 "silver.excluded": privacy.pii_scan(excl, ["description"])}
        fact = pd.read_parquet(staging["fact_sales_line"], columns=["customer_key", "country", "customer_identified"])
        per_country = fact[fact.customer_identified].groupby("country")["customer_key"].nunique()
        small = sorted(per_country[per_country < cfg["privacy"]["small_cell_threshold"]].index.tolist())
        # raw-id leakage check: published tables must not contain any column named like a raw id
        leaks = [n for n, p in staging.items() if any("customer id" in c.lower() or c.lower() == "customer_id" for c in pd.read_parquet(p).columns)]
        res = {
            "published_pii_hits": privacy.scan_total({"x": scans["published.dim_product"]["description"]}),
            "scans_hit_counts": scans, "raw_customer_id_columns_in_outputs": leaks,
            "pseudonymisation": {"method": "HMAC-SHA256 keyed pseudonym, truncated to %d hex chars" % cfg["privacy"]["pseudonym_hex_length"],
                                 "key_id": clean_summary["key_id"], "secret_source": f"environment variable {cfg['privacy']['secret_env_var']}",
                                 "accuracy_note": "Pseudonymous, not anonymous; re-linkable by whoever holds the secret or raw ids."},
            "inventory": privacy.identifier_inventory({"staff_name_rows_raw": clean_summary["staff_name_pattern_rows_raw"], "small_cell_countries": small}),
        }
        if leaks:
            res["published_pii_hits"] += len(leaks)
        s["rows_out"] = len(fact)
    _write_json(ctx.report_dir / "privacy_report.json", res)
    return res


@task(name="publish")  # no retries: gate failures are deterministic and must not be retried
def t_publish(cfg: dict, ctx: config.RunContext, m: dict, clean_summary: dict, staging: dict, bronze_validation: dict,
              validation_results: dict, privacy_result: dict, _bias_done: dict) -> dict:
    a = audit_for(ctx)
    paths = {k: Path(v) for k, v in staging.items()}
    return publish.publish(ctx, cfg, paths, validation_results, bronze_validation, privacy_result, m, clean_summary["key_id"], audit=a)


@task(name="evidence_summary")
def t_summary(cfg: dict, ctx: config.RunContext, m: dict, clean_summary: dict, validation_results: dict, bronze_validation: dict,
              privacy_result: dict, manifest: dict, started: float) -> dict:
    a = audit_for(ctx)
    ev = clean_summary["overlap_evidence"]
    summary = {
        "run_id": ctx.run_id, "status": "SUCCEEDED", "pipeline_version": __version__, "rules_version": ctx.rules_version,
        "rules_hash": ctx.rules_hash, "code_hash": ctx.code_hash, "build_id": manifest["build_id"],
        "great_expectations_version": validation_results["great_expectations_version"],
        "source": {"file": m["source_file"], "sha256": m["source_sha256"], "rows": m["rows"], "meets_min_5000": m["rows_meets_minimum"]},
        "dispositions": {k: clean_summary[k] for k in ("rows_raw", "rows_retained", "rows_quarantined", "rows_excluded")},
        "reason_counts": clean_summary["reason_counts"], "overlap_evidence": ev,
        "retained_exact_duplicate_rows_flagged": clean_summary["retained_exact_duplicate_rows_flagged"],
        "validation": {
            "bronze": {k: bronze_validation[k] for k in ("expectations_evaluated", "expectations_passed", "critical_failures", "warning_failures")},
            "outputs": {k: validation_results[k] for k in ("expectations_evaluated", "expectations_passed", "critical_failures", "warning_failures")},
            "reconciliation_checks": len(validation_results["reconciliation"]),
            "reconciliation_passed": sum(r["within_tolerance"] for r in validation_results["reconciliation"]),
        },
        "published_tables": {k: v["rows"] for k, v in manifest["tables"].items()},
        "privacy": {"published_pii_hits": privacy_result["published_pii_hits"], "key_id": clean_summary["key_id"]},
        "runtime_seconds": round(time.time() - started, 1),
    }
    # audit-log leak check: no customer pseudonym and no secret may appear in the log
    a.event("RUN", "pipeline", task="evidence_summary", outcome="succeeded")
    log_text = a.path.read_text()
    keys = pd.read_parquet(Path(manifest and ctx.run_dir / "staging" / "dim_customer.parquet"), columns=["customer_key"])["customer_key"]
    summary["audit_log"] = {"events": log_text.count("\n"), "contains_any_customer_key": bool(any(k in log_text for k in keys.sample(min(len(keys), 2000), random_state=0))),
                            "contains_secret": bool(os.environ.get(cfg["privacy"]["secret_env_var"], "\x00") in log_text)}
    _write_json(ctx.report_dir / "run_summary.json", summary)
    _write_json(ctx.report_dir / "run_status.json", {"run_id": ctx.run_id, "status": "SUCCEEDED"})
    latest = ctx.root / "reports" / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(ctx.report_dir, latest)
    return summary


# ------------------------------------------------------------------------------------------------ flow
@flow(name="retail-analytics-pipeline", retries=0)
def retail_pipeline(config_path: str | None = None, run_id: str | None = None, root: str | None = None) -> dict:
    started = time.time()
    cfg = config.load_config(Path(config_path) if config_path else None)
    ctx = config.new_run(cfg, run_id=run_id, root=Path(root) if root else None)
    ctx.report_dir.mkdir(parents=True, exist_ok=True)
    secret = privacy.load_secret(cfg)  # fail fast and clearly if missing/weak (message never echoes the value)
    audit = AuditLogger(ctx, ctx.report_dir / "audit_events.jsonl", forbidden_values=[secret.decode()])
    _AUDITS[ctx.run_id] = audit
    log = _logger()
    audit.event("RUN", "pipeline", task="flow", outcome="started")
    log.info("run %s started (rules %s, code %s)", ctx.run_id, ctx.rules_version, ctx.code_hash)
    ctx_failed: list[str] = []
    try:
        m = t_ingest.submit(cfg, ctx)
        prof = t_profile.submit(cfg, ctx, m)
        vb = t_validate_bronze.submit(cfg, ctx, m)
        cl = t_clean.submit(cfg, ctx, m, vb)
        fp = t_transform.submit(cfg, ctx, cl)
        st = t_integrate.submit(cfg, ctx, fp, cl)
        vo = t_validate_outputs.submit(cfg, ctx, m, cl, st)
        bi = t_bias.submit(cfg, ctx, cl, st)
        pr = t_privacy.submit(cfg, ctx, m, cl, st)
        pb = t_publish.submit(cfg, ctx, m, cl, st, vb, vo, pr, bi)
        sm = t_summary.submit(cfg, ctx, m, cl, vo, vb, pr, pb, started, wait_for=[prof])
        ordered = {"ingest": m, "profile_source": prof, "validate_bronze": vb, "clean": cl, "transform": fp, "integrate": st,
                   "validate_outputs": vo, "bias_detection": bi, "privacy_scan": pr, "publish": pb, "evidence_summary": sm}
        failed = []
        for name, fut in ordered.items():
            fut.wait()
            if fut.state.is_failed() or fut.state.is_crashed():
                failed.append(name)
        if failed:  # re-raise the ROOT CAUSE (first failed task in dependency order), not a downstream 'pending' symptom
            ctx_failed.extend(failed)
            ordered[failed[0]].result()
        return sm.result()
    except BaseException as exc:  # record, then re-raise so the flow run is marked Failed
        audit.event("RUN", "pipeline", task="flow", outcome="failed", error_class=type(exc).__name__, failed_tasks=",".join(ctx_failed))
        _write_json(ctx.report_dir / "run_status.json", {"run_id": ctx.run_id, "status": "FAILED", "error_class": type(exc).__name__,
                                                          "failed_tasks": ctx_failed, "error": str(exc)[:500], "published": False})
        log.error("run %s FAILED (%s); nothing was published", ctx.run_id, type(exc).__name__)
        raise


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Run the retail analytics pipeline")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    out = retail_pipeline(config_path=a.config, run_id=a.run_id, root=a.root)
    print(json.dumps({k: out[k] for k in ("run_id", "status", "dispositions", "validation", "published_tables", "runtime_seconds")}, indent=2))
    sys.exit(0)
