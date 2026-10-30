"""MLflow setup. Local SQLite backend + local artifact folder; nothing is logged here (runs are created only by real experiments).
Launch the UI:  mlflow ui --backend-store-uri sqlite:///mlruns_store/mlflow.db --default-artifact-root mlruns_store/artifacts --port 5000"""
from pathlib import Path
import mlflow, yaml

ROOT = Path(__file__).resolve().parents[2]
ITERATION = "2"   # iteration 1 (superseded) is kept in MLflow and reports/model/iteration1

def cfg():
    return yaml.safe_load((ROOT / "configs" / "churn.yaml").read_text())

def setup():
    c = cfg()["mlflow"]
    store = ROOT / "mlruns_store"; (store / "artifacts").mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{store / 'mlflow.db'}")
    if mlflow.get_experiment_by_name(c["experiment"]) is None:
        mlflow.create_experiment(c["experiment"], artifact_location=(store / "artifacts").as_uri())
    mlflow.set_experiment(c["experiment"])
    return c["experiment"]
