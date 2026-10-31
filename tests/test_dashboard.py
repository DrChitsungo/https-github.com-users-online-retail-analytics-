"""Tests for the Module 5 dashboard: metric maths, Module 4 scenario parity, API client behaviour, privacy of the evidence file, and Streamlit smoke runs.
Needs requirements-ml.txt plus dashboard/requirements.txt; skips cleanly where streamlit/plotly are not installed (Module 3 CI job)."""
import json, re, sys
from pathlib import Path
import pytest
for _m in ("streamlit", "plotly", "requests", "sklearn", "fastapi", "httpx", "joblib"): pytest.importorskip(_m)
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard")); sys.path.insert(0, str(ROOT / "src"))
from dash_lib.core import ApiClient, apply_scenario, load_evidence, metrics_from_counts, to_payload
from fastapi.testclient import TestClient
from churn_model.api import app as api_app
E = load_evidence(); tc = TestClient(api_app)

def test_filter_grid_reproduces_recorded_test_metrics():
    rec = json.loads((ROOT / "reports/model/final_test_results.json").read_text())["models"]["logreg"]["test"]; m = metrics_from_counts(E["filter_grid"]["All|All"])
    for k in ("precision", "recall", "f1", "accuracy", "flag_rate"): assert m[k] == pytest.approx(rec[k], abs=1e-9)
    g = E["filter_grid"]; assert g["All|UK"]["n"] + g["All|Non-UK"]["n"] == g["All|All"]["n"] and g["2011-08|All"]["n"] + g["2011-09|All"]["n"] == g["All|All"]["n"]

def test_undefined_metrics_are_none_not_zero():
    m = metrics_from_counts({"n": 10, "tp": 0, "fp": 0, "fn": 0, "tn": 10}); assert m["precision"] is None and m["recall"] is None and m["f1"] is None and m["small_sample"]

@pytest.mark.parametrize("k,r", [(0, 30), (1, 1), (3, 30), (6, 90)])
def test_scenario_matches_module4_counterfactual_method(k, r):
    explain = pytest.importorskip("churn_model.explain")
    for c in E["cases"].values():
        base = c["profile"]; mine = apply_scenario(base, k, r); ref = explain.apply_scenario(pd.Series({f: (float("nan") if v is None else v) for f, v in base.items()}), k, r)
        for f, v in mine.items():
            if v is None or v != v: assert ref[f] != ref[f]
            else: assert float(ref[f]) == pytest.approx(float(v), rel=1e-9)

def test_all_example_profiles_and_scenarios_are_accepted_by_the_api():
    for c in E["cases"].values():
        for k, r in ((0, 30), (3, 30), (6, 1), (2, 90)):
            resp = tc.post("/predict", json=to_payload(apply_scenario(c["profile"], k, r))); assert resp.status_code == 200, resp.text

def test_live_scores_close_to_stored_scores():
    for c in E["cases"].values():
        assert abs(tc.post("/predict", json=to_payload(c["profile"])).json()["churn_probability"] - c["stored_score"]) < 0.002   # rounding for privacy only

def test_invalid_profile_is_rejected_without_echoing_values():
    c = next(iter(E["cases"].values()))["profile"]; r = tc.post("/predict", json=to_payload(c) | {"tenure_days": 5.0, "recency_days": 100.0}); assert r.status_code == 422 and "100.0" not in r.text

def test_client_reports_unreachable_api_and_returns_no_score():
    x = ApiClient("http://127.0.0.1:9", timeout=1).predict({}); assert not x["ok"] and "No score was produced" in x["error"] and "body" not in x

def test_evidence_file_has_no_identifiers_or_row_level_records():
    s = (ROOT / "dashboard/data/dashboard_evidence.json").read_text()
    assert "customer_key" not in s and not re.search(r"\b[0-9a-f]{32,64}\b", s.replace(E["meta"]["mlflow"]["validation_run_id"], "").replace(E["meta"]["mlflow"]["test_run_id"], ""))
    assert all("row" not in c for c in E["cases"].values()) and len(s) < 200_000

# ---------------------------------------------------------------- Streamlit smoke tests
from streamlit.testing.v1 import AppTest
VIEWS = ["Business overview", "Results and explanations", "Prediction and what-if", "Fairness and ethics", "About and evidence"]

def run(view, monkeypatch=None, api_url=None):
    at = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=60)
    if api_url: import os; os.environ["CHURN_API_URL"] = api_url
    at.run(); at.sidebar.radio[0].set_value(view); at.run(); return at

@pytest.mark.parametrize("view", [v for v in VIEWS if v != "Prediction and what-if"])
def test_static_views_render_without_exception(view):
    at = run(view); assert not at.exception, at.exception

def test_fairness_view_states_missing_protected_attributes_and_no_compliance_claim():
    at = run("Fairness and ethics"); txt = " ".join(e.value for e in at.error) + " ".join(m.value for m in at.markdown)
    plain = txt.replace("*", ""); assert "No protected attributes" in plain and "not a regulatory" in plain
    assert "certified" not in txt.lower() and "legally compliant" not in txt.lower()

def test_prediction_view_shows_error_and_no_score_when_api_down(monkeypatch):
    monkeypatch.setenv("CHURN_API_URL", "http://127.0.0.1:9"); at = run("Prediction and what-if"); assert not at.exception
    assert any("Cannot reach the model API" in e.value for e in at.error) and not at.button

def test_prediction_view_calls_the_api_and_shows_live_scores(monkeypatch):
    import requests
    def fake(method, url, timeout=None, **kw):
        path = "/" + url.split("//", 1)[1].split("/", 1)[1]; r = tc.request(method, path, **kw)
        class R:
            status_code = r.status_code; headers = r.headers
            def json(self): return r.json()
        return R()
    monkeypatch.setattr(requests, "request", fake); monkeypatch.setenv("CHURN_API_URL", "http://testserver")
    at = run("Prediction and what-if"); assert not at.exception and any("Model API reachable" in s.value for s in at.success)
    at.button[0].click(); at.run(); assert not at.exception
    assert any("live API" in m.label for m in at.metric), [m.label for m in at.metric]
