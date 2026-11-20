"""Release gates for the churn model (capstone report, Section 10).

Run:  PYTHONPATH=src python -m churn_model.release_gates            # exits 1 if any automated gate fails
      PYTHONPATH=src python -m churn_model.release_gates --out reports/release_gates/latest.json

Gates read only committed, aggregate evidence (no customer-level data), so they run in CI:
  1 data quality   - the Module 3 run succeeded, no critical Great Expectations failures, all reconciliations passed, no PII published
  2 integrity      - the packaged model file is byte-identical to the registry champion; threshold, dataset hash and churn definition agree
  3 performance    - test AUC, lift over the recency rule, recall, precision lift and Brier meet configs/release_gates.yaml
  4 fairness       - UK vs non-UK disparate impact and TPR/FPR ratios inside the Module 1/2 bands; validation fairness gate passed
  5 human approval - recorded as REQUIRED; never automated
A failed automated gate keeps the current champion (the script changes nothing; it only reports and sets the exit code).
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load(p):
    p = ROOT / p
    return yaml.safe_load(p.read_text()) if p.suffix in (".yaml", ".yml") else json.loads(p.read_text())


def _check(name, ok, detail):
    return {"check": name, "passed": bool(ok), "detail": detail}


def gate_data_quality(c):
    s = _load(c["run_summary"]); v = s["validation"]
    return [
        _check("pipeline run status", s["status"] == c["require_status"], s["status"]),
        _check("critical GX failures (bronze)", v["bronze"]["critical_failures"] <= c["max_critical_failures"], v["bronze"]["critical_failures"]),
        _check("critical GX failures (outputs)", v["outputs"]["critical_failures"] <= c["max_critical_failures"], v["outputs"]["critical_failures"]),
        _check("reconciliation checks", (v["reconciliation_passed"] == v["reconciliation_checks"]) or not c["require_all_reconciliation"],
               f'{v["reconciliation_passed"]}/{v["reconciliation_checks"]}'),
        _check("published PII hits", s["privacy"]["published_pii_hits"] <= c["max_published_pii_hits"], s["privacy"]["published_pii_hits"]),
    ]


def gate_integrity(c, perf_results):
    meta, reg, cfg = _load(c["metadata_file"]), _load(c["registry_file"]), _load(c["churn_config"])
    sha = hashlib.sha256((ROOT / c["model_file"]).read_bytes()).hexdigest()
    return [
        _check("model file matches registry champion", sha == reg["sha256"] and reg.get("alias") == "champion", f"{sha[:12]} vs {reg['sha256'][:12]} ({reg.get('alias')})"),
        _check("threshold agrees (metadata vs evaluation)", abs(meta["threshold"] - perf_results["threshold"]) < 1e-9, meta["threshold"]),
        _check("dataset hash agrees (metadata vs registry)", meta["dataset_hash"] == reg["tags"]["dataset_hash"], meta["dataset_hash"]),
        _check("churn horizon is the agreed 90 days", cfg["task"]["horizon_days"] == c["required_horizon_days"], cfg["task"]["horizon_days"]),
        _check("eligibility is the agreed 180 days", cfg["task"]["min_history_days"] == c["required_min_history_days"], cfg["task"]["min_history_days"]),
    ]


def gate_performance(c, r):
    m = r["models"][c["model_key"]]["test"]; rule = r["models"][c["rule_key"]]["test"]; base_rate = r["test_prevalence"]
    return [
        _check("test ROC-AUC", m["roc_auc"] >= c["min_roc_auc"], f'{m["roc_auc"]:.3f} >= {c["min_roc_auc"]}'),
        _check("AUC lift over recency rule", m["roc_auc"] - rule["roc_auc"] >= c["min_auc_lift_over_rule"], f'{m["roc_auc"] - rule["roc_auc"]:+.3f} >= {c["min_auc_lift_over_rule"]}'),
        _check("recall", m["recall"] >= c["min_recall"], f'{m["recall"]:.3f} >= {c["min_recall"]}'),
        _check("precision lift over base rate", m["precision"] - base_rate >= c["min_precision_lift_over_base_rate"], f'{m["precision"] - base_rate:+.3f} >= {c["min_precision_lift_over_base_rate"]}'),
        _check("Brier score beats recency rule", (m["brier"] < rule["brier"]) or not c["brier_must_beat_rule"], f'{m["brier"]:.3f} < {rule["brier"]:.3f}'),
    ]


def gate_fairness(c, r):
    f = r["fairness"]; lo, hi = c["disparate_impact_band"]; rlo, rhi = c["relative_band"]; out = []
    for grp, cmp_ in f["comparisons"].items():
        if cmp_["n"] < c["min_group_n"]:
            out.append(_check(f"{grp}: group large enough to judge", False, f'n={cmp_["n"]} < {c["min_group_n"]}')); continue
        out += [
            _check(f"{grp}: disparate impact", lo <= cmp_["disparate_impact_ratio"] <= hi, f'{cmp_["disparate_impact_ratio"]:.3f} in [{lo}, {hi}]'),
            _check(f"{grp}: TPR vs overall", rlo <= cmp_["tpr_vs_overall"] <= rhi, f'{cmp_["tpr_vs_overall"]:.3f} in [{rlo}, {rhi}]'),
            _check(f"{grp}: FPR vs overall", rlo <= cmp_["fpr_vs_overall"] <= rhi, f'{cmp_["fpr_vs_overall"]:.3f} in [{rlo}, {rhi}]'),
        ]
    if c.get("require_validation_gate"):
        sel = _load(c["selection_file"]); g = sel["fairness_gate_validation"][sel["final_model"]]
        out.append(_check("validation fairness gate (selection)", g["passes"], f'FPR vs overall {g["fpr_vs_overall"]:.3f}'))
    return out


def evaluate(cfg: dict) -> dict:
    r = _load(cfg["performance"]["results_file"])
    gates = {
        "1_data_quality": gate_data_quality(cfg["data_quality"]),
        "2_integrity": gate_integrity(cfg["integrity"], r),
        "3_performance": gate_performance(cfg["performance"], r),
        "4_fairness": gate_fairness(cfg["fairness"], r),
    }
    summary = {k: all(c["passed"] for c in v) for k, v in gates.items()}
    auto_pass = all(summary.values())
    return {
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": _load(cfg["integrity"]["metadata_file"])["model_version"],
        "gates": gates, "gate_summary": summary,
        "automated_gates_passed": auto_pass,
        "5_human_approval": {"required": cfg["approval"]["required"], "approver_role": cfg["approval"]["approver_role"], "status": "PENDING"},
        "decision": ("automated gates passed; promotion still requires human approval" if auto_pass
                     else "BLOCKED: keep the current champion and open a documented review"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/release_gates.yaml"); ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = evaluate(_load(a.config))
    for g, checks in res["gates"].items():
        print(f"{'PASS' if res['gate_summary'][g] else 'FAIL'}  {g}")
        for c in checks: print(f"   {'ok ' if c['passed'] else 'XX '} {c['check']}: {c['detail']}")
    print("     5_human_approval: REQUIRED (pending)")
    print(res["decision"])
    if a.out:
        out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, indent=2) + "\n")
    return 0 if res["automated_gates_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
