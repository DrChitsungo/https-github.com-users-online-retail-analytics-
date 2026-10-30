"""Cross-artefact consistency check for Module 4. Exits non-zero on any mismatch. Run: PYTHONPATH=src python scripts/verify_module4.py"""
import json, re, sys
from pathlib import Path
import joblib, mlflow, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; bad = []
def chk(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else "")); (None if ok else bad.append(name))
meta = json.loads((ROOT/"models/churn_logreg_v1.0.0.metadata.json").read_text()); test = json.loads((ROOT/"reports/model/final_test_results.json").read_text())
sel = json.loads((ROOT/"reports/model/selection.json").read_text()); stage1 = json.loads((ROOT/"reports/model/stage1_validation_results.json").read_text())
model = joblib.load(ROOT/"models/churn_logreg_v1.0.0.joblib")
chk("selection final model is logreg", sel["final_model"] == "logreg" == test["final_model"])
chk("metadata test AUC == final_test_results", abs(meta["test"]["roc_auc"] - test["models"]["logreg"]["test"]["roc_auc"]) < 1e-12)
chk("metadata val AUC == stage1 results", abs(meta["validation"]["roc_auc"] - stage1["results"]["logreg"]["val"]["roc_auc"]) < 1e-12)
chk("threshold identical (metadata, test results)", abs(meta["threshold"] - test["threshold"]) < 1e-9)
chk("dataset hash identical (metadata, selection, stage1)", meta["dataset_hash"] == sel["dataset_hash"] == stage1["dataset_hash"])
chk("code hash identical (metadata, selection, stage1)", meta["code_hash"] == sel["code_hash_at_selection"] == stage1["code_hash"])
chk("selection written before test evaluation", sel["written_before_test_evaluation"] is True and sel["iteration"] == "2")
mlflow.set_tracking_uri("sqlite:///" + str(ROOT/"mlruns_store/mlflow.db"))
for k in ("validation_run_id", "test_run_id"):
    r = mlflow.get_run(meta["mlflow"][k]); chk(f"MLflow {k} exists and FINISHED", r.info.status == "FINISHED", r.data.tags.get("mlflow.runName", ""))
tr = mlflow.get_run(meta["mlflow"]["test_run_id"]); chk("MLflow test AUC == metadata", abs(tr.data.metrics["test_roc_auc"] - meta["test"]["roc_auc"]) < 1e-12)
chk("MLflow dataset_hash param == metadata", tr.data.params["dataset_hash"] == meta["dataset_hash"])
from churn_model.api import app, FEATURES, THRESHOLD, VERSION
from fastapi.testclient import TestClient
info = TestClient(app).get("/model").json()
chk("API version/threshold/features == metadata", info["model_version"] == meta["model_version"] == VERSION and abs(THRESHOLD - meta["threshold"]) < 1e-9 and info["features"] == meta["feature_order"] == FEATURES)
rep = (ROOT/"reports/Model_Validation_Report.md").read_text(); card = (ROOT/"docs/MODEL_CARD.md").read_text(); fr = (ROOT/"reports/Fairness_Metrics_Report.md").read_text()
t = test["models"]["logreg"]["test"]; ci = test["models"]["logreg"]["ci"]["roc_auc"]
for label, s in (("report", rep), ("model card", card)):
    chk(f"{label} quotes test AUC {t['roc_auc']:.3f} and CI", f"{t['roc_auc']:.3f}" in s and f"{ci[0]:.3f}" in s and f"{ci[1]:.3f}" in s)
    chk(f"{label} names version 1.0.0 / threshold", "1.0.0" in s and ("0.314" in s or "0.313903" in s))
c = test["fairness"]["comparisons"]["Non-UK"]
for label, s in (("report", rep), ("fairness report", fr), ("model card", card)):
    chk(f"{label} quotes DI {c['disparate_impact_ratio']:.3f} and FPR ratio {c['fpr_vs_overall']:.3f}", f"{c['disparate_impact_ratio']:.3f}" in s and f"{c['fpr_vs_overall']:.3f}" in s)
chk("model card mentions both MLflow run ids", meta["mlflow"]["validation_run_id"] in card and meta["mlflow"]["test_run_id"] in card)
chk("no secrets or raw ids in reports", not re.search(r"(?i)customer_key\s*[:=]\s*[0-9a-f]{16}|CUSTOMER_KEY_SECRET\s*=\s*\w{16}", rep + card + fr))
chk("AI disclosure marked pending in report, card checklist", "pending" in rep.lower() and "Pending" in (ROOT/"docs/requirements_evidence_checklist.md").read_text())
print("\nRESULT:", "ALL CHECKS PASSED" if not bad else f"{len(bad)} FAILED: {bad}"); sys.exit(1 if bad else 0)
