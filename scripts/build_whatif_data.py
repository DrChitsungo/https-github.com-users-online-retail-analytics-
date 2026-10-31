"""Scenario scores for the Module 5 deck's what-if slide. Scores come from the Module 4 API code (FastAPI TestClient, same model file), never typed by hand.
Run: PYTHONPATH=src:dashboard python scripts/build_whatif_data.py  -> deck/whatif_data.json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / "src"), str(ROOT / "dashboard")]
from fastapi.testclient import TestClient
from churn_model.api import app, THRESHOLD, VERSION
from dash_lib.core import apply_scenario, load_evidence, to_payload
tc = TestClient(app); E = load_evidence(); out = {"model_version": VERSION, "threshold": THRESHOLD, "latest_purchase_days_before_T": 90, "cases": {}}
for key in ("A_typical_true_positive", "C_confident_false_positive"):
    base = E["cases"][key]["profile"]; scores = []
    for k in range(0, 7):
        r = tc.post("/predict", json=to_payload(apply_scenario(base, k, 90))); assert r.status_code == 200, r.text; scores.append(round(r.json()["churn_probability"], 4))
    out["cases"][key] = {"label": E["cases"][key]["label"], "scores_by_extra_invoices": scores}
Path(ROOT / "deck/whatif_data.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out))
