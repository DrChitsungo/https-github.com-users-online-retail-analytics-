"""Register the serialised final model in the MLflow Model Registry (version + alias).

The registry version points at the artifact of the validation run that produced the model, so its lineage is
run -> model version. It creates no new experiment run. MLflow 3 replaced the old Staging/Production stages with
aliases, so the stage is recorded as the alias `champion` (the version currently approved for the API) plus tags.
The alias is NOT production approval: the churn window is PROPOSED and the fairness gap is unresolved.
Run: PYTHONPATH=src python -m churn_model.register_model   (idempotent)"""
import hashlib, json
import mlflow
from mlflow.tracking import MlflowClient
from . import tracking

REGISTERED_NAME = "retail-churn-logreg"
ALIAS = "champion"

def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    tracking.setup(); client = MlflowClient()
    meta_path = next((tracking.ROOT / "models").glob("churn_*_v*.metadata.json")); meta = json.loads(meta_path.read_text())
    joblib_path = meta_path.with_name(meta_path.name.replace(".metadata.json", ".joblib")); digest = sha256(joblib_path)
    run_id = meta["mlflow"]["validation_run_id"]
    art = client.list_artifacts(run_id, "model"); assert art and art[0].path.endswith(".joblib"), "validation run has no model artifact"
    local = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path=art[0].path)
    from pathlib import Path
    assert sha256(Path(local)) == digest, "registry source artifact must be byte-identical to the serialised model"

    try: client.create_registered_model(REGISTERED_NAME, description="90-day customer churn, logistic regression (Module 4). Pseudonymous customer-level data; for human-reviewed retention planning only.")
    except mlflow.exceptions.MlflowException: pass
    existing = [v for v in client.search_model_versions(f"name='{REGISTERED_NAME}'") if v.tags.get("model_version") == meta["model_version"] and v.tags.get("sha256") == digest]
    if existing: mv = existing[0]; print("already registered: version", mv.version)
    else:
        mv = client.create_model_version(REGISTERED_NAME, source=f"runs:/{run_id}/{art[0].path}", run_id=run_id,
                                         description=f"churn_logreg v{meta['model_version']}; threshold {meta['threshold']:.6f} (max F1 on validation)")
        for k, v in {"model_version": meta["model_version"], "sha256": digest, "iteration": meta["iteration"], "threshold": f"{meta['threshold']:.6f}",
                     "test_roc_auc": f"{meta['test']['roc_auc']:.3f}", "test_run_id": str(meta["mlflow"]["test_run_id"]), "dataset_hash": meta["dataset_hash"],
                     "status_note": "validated on time-based test; not production-approved (PROPOSED churn window; UK vs non-UK FPR gap unresolved)"}.items():
            client.set_model_version_tag(REGISTERED_NAME, mv.version, k, v)
        print("registered: version", mv.version)
    client.set_registered_model_alias(REGISTERED_NAME, ALIAS, mv.version)

    got = client.get_model_version_by_alias(REGISTERED_NAME, ALIAS)
    rec = {"registered_model": REGISTERED_NAME, "version": got.version, "alias": ALIAS, "source": got.source, "run_id": got.run_id, "sha256": got.tags.get("sha256"),
           "tags": dict(got.tags), "tracking_store": "sqlite:///mlruns_store/mlflow.db (local, not committed)"}
    meta["registry"] = {k: rec[k] for k in ("registered_model", "version", "alias", "run_id")}
    meta_path.write_text(json.dumps(meta, indent=2, default=float))
    out = tracking.ROOT / "reports" / "mlflow_evidence" / "model_registry.json"; out.write_text(json.dumps(rec, indent=2))
    print(json.dumps(rec, indent=1))

if __name__ == "__main__":
    main()
