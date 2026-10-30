"""Serialise the selected fitted pipeline (imputer + log1p + scaler + logistic regression) with a metadata sidecar.
Run: PYTHONPATH=src python -m churn_model.package_model"""
import json, shutil
import joblib, mlflow, numpy as np, pandas as pd
from . import dataset as D, tracking
from .common import env_versions

VERSION = "1.0.0"

def main():
    R = tracking.ROOT / "reports" / "model"; sel = json.loads((R / "selection.json").read_text()); s1 = json.loads((R / "stage1_validation_results.json").read_text())
    fin = json.loads((R / "final_test_results.json").read_text()); name = sel["final_model"]
    dst = tracking.ROOT / "models" / f"churn_{name}_v{VERSION}.joblib"; shutil.copy(tracking.ROOT / "models" / "candidates" / f"{name}.joblib", dst)
    pipe = joblib.load(dst)
    te = pd.read_parquet(tracking.ROOT / "data" / "modeling" / "churn_snapshots.parquet"); te = te[D.split_masks(te, tracking.cfg())["test"]].reset_index(drop=True)
    pr = pd.read_parquet(tracking.ROOT / "data" / "modeling" / "test_predictions.parquet")
    assert np.allclose(pipe.predict_proba(te[D.FEATURES])[:, 1], pr.p.values), "serialised model must reproduce the stored test predictions"
    tracking.setup(); runs = mlflow.search_runs(experiment_names=[tracking.cfg()["mlflow"]["experiment"]], filter_string="tags.iteration = '2'")
    def rid(stage, kind_name):
        r = runs[(runs["tags.stage"] == stage) & (runs["tags.mlflow.runName"].str.contains(kind_name))]; return None if r.empty else r.sort_values("start_time").iloc[-1]["run_id"]
    meta = {"model_name": "churn_logreg", "model_version": VERSION, "iteration": tracking.ITERATION, "task": "customer_churn_90d", "positive_class": "churn: no sales invoice in the 90 days after the prediction date",
            "threshold": s1["results"][name]["threshold"], "threshold_source": "maximises F1 on validation dates (2011-03, 2011-04); not tuned on test",
            "feature_order": D.FEATURES, "features_allowed_missing": ["mean_gap_days", "std_gap_days", "recency_over_gap"], "imputation": "median from training rows (inside pipeline)",
            "dataset_hash": s1["dataset_hash"], "fact_table_sha256": s1["fact_table_sha256"], "code_hash": s1["code_hash"], "config_hash": s1["config_hash"], "versions": env_versions(),
            "validation": {k: s1["results"][name]["val"][k] for k in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy", "n")},
            "test": {k: fin["models"][name]["test"][k] for k in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy", "n")}, "test_ci95": fin["models"][name]["ci"],
            "mlflow": {"experiment": tracking.cfg()["mlflow"]["experiment"], "validation_run_id": s1["results"][name]["run_id"], "test_run_id": rid("test", f"test-eval-{name}")},
            "hyperparameters": {k: v for k, v in s1["results"][name].items() if k.startswith("best_")}, "intended_use": "rank currently active, identified customers by 90-day churn risk to support human-reviewed retention planning",
            "not_for": ["automated decisions about individuals (credit terms, exclusions)", "unidentified customers", "customers inactive for more than 180 days", "inference of personal characteristics"]}
    (tracking.ROOT / "models" / f"churn_{name}_v{VERSION}.metadata.json").write_text(json.dumps(meta, indent=2, default=float))
    print(dst.name, dst.stat().st_size, "bytes"); print(json.dumps({k: meta[k] for k in ("model_version", "threshold", "mlflow", "test")}, indent=1, default=float))

if __name__ == "__main__":
    main()
