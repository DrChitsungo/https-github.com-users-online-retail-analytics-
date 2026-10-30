"""Tests for the churn modelling layer: leakage, label construction, split geometry, preprocessing, serialisation, fairness maths and the API.
Dataset-dependent checks skip automatically when the (git-ignored) modelling table is absent."""
import json
from pathlib import Path
import joblib, numpy as np, pandas as pd, pytest
from fastapi.testclient import TestClient
from churn_model import dataset as D, fairness as F, tracking
from churn_model.api import app, FEATURES as API_FEATURES, THRESHOLD
from churn_model.common import forward_chain_folds, make_pipeline

ROOT = tracking.ROOT; CFG = tracking.cfg()
VALID = {"recency_days": 40, "tenure_days": 400, "n_inv_all": 6, "n_inv_30": 0, "n_inv_90": 1, "n_inv_prev90": 2, "rev_all": 1800.5, "rev_90": 300, "rev_180": 900,
         "n_products_all": 60, "n_products_180": 35, "avg_units_per_inv": 120, "mean_gap_days": 55, "std_gap_days": 20, "recency_over_gap": 0.73, "n_cancel_all": 0, "cancel_ratio": 0}

def toy_events():
    d = lambda s: pd.Timestamp(s)
    inv = pd.DataFrame([("A", "i1", d("2010-01-10"), 100, 5, 3, "United Kingdom"), ("A", "i2", d("2010-05-20"), 50, 2, 2, "United Kingdom"), ("A", "i3", d("2010-07-15"), 70, 4, 3, "United Kingdom"),
                        ("B", "i4", d("2010-01-05"), 30, 1, 1, "France"), ("C", "i5", d("2010-06-20"), 80, 3, 2, "France"), ("C", "i6", d("2010-09-10"), 60, 2, 2, "France")],
                       columns=["customer_key", "invoice_no", "date", "revenue", "units", "n_products", "country"])
    canc = pd.DataFrame([("A", "c1", d("2010-06-01"))], columns=["customer_key", "invoice_no", "date"])
    prod = pd.DataFrame([(r.customer_key, r.date, f"s{k}") for r in inv.itertuples() for k in range(r.n_products)], columns=["customer_key", "invoice_date", "stock_code"])
    return inv, canc, prod

def test_label_is_no_invoice_in_horizon_and_eligibility_is_lookback():
    inv, canc, prod = toy_events(); T = pd.Timestamp("2010-08-01"); s = D.build_snapshot(T, inv, canc, prod).set_index("customer_key")
    assert set(s.index) == {"A", "C"}                       # B last bought 2010-01-05 (>180d); not eligible
    assert s.loc["A", "churn"] == 1                          # A has no invoice in [2010-08-01, 2010-10-30)
    assert s.loc["C", "churn"] == 0                          # C buys on 2010-09-10 -> retained

def test_features_do_not_use_data_on_or_after_prediction_date():
    inv, canc, prod = toy_events(); T = pd.Timestamp("2010-08-01"); base = D.build_snapshot(T, inv, canc, prod).set_index("customer_key")[D.FEATURES]
    inv2 = inv.copy(); inv2.loc[inv2.date >= T, "revenue"] *= 1000; inv2.loc[inv2.date >= T, "units"] += 999
    extra = pd.DataFrame([("A", "x1", T, 500, 9, 9, "United Kingdom"), ("C", "x2", T + pd.Timedelta(days=5), 500, 9, 9, "France")], columns=inv.columns); inv2 = pd.concat([inv2, extra])
    prod2 = pd.concat([prod, pd.DataFrame([("A", T, "zz"), ("C", T + pd.Timedelta(days=5), "zz")], columns=prod.columns)])
    canc2 = pd.concat([canc, pd.DataFrame([("A", "c9", T + pd.Timedelta(days=3))], columns=canc.columns)])
    after = D.build_snapshot(T, inv2, canc2, prod2).set_index("customer_key")[D.FEATURES]
    pd.testing.assert_frame_equal(base, after)

def test_label_changes_when_future_purchase_added_but_features_do_not():
    inv, canc, prod = toy_events(); T = pd.Timestamp("2010-08-01")
    a = D.build_snapshot(T, inv, canc, prod).set_index("customer_key")
    inv2 = pd.concat([inv, pd.DataFrame([("A", "x", pd.Timestamp("2010-08-20"), 10, 1, 1, "United Kingdom")], columns=inv.columns)])
    b = D.build_snapshot(T, inv2, canc, prod).set_index("customer_key")
    assert a.loc["A", "churn"] == 1 and b.loc["A", "churn"] == 0

def test_no_evaluation_only_or_identifier_columns_are_predictors():
    assert not set(D.FEATURES) & set(D.EVAL_ONLY)
    assert not any(k in f for f in D.FEATURES for k in ("country", "group", "customer", "snapshot", "month"))

def test_split_geometry_purges_outcome_windows_and_respects_data_end():
    H = CFG["task"]["horizon_days"]; sp = {k: tuple(pd.Timestamp(x) for x in v) for k, v in CFG["split"].items()}
    assert sp["train"][1] + pd.Timedelta(days=H) <= sp["validation"][0] and sp["validation"][1] + pd.Timedelta(days=H) <= sp["test"][0]
    assert pd.Timestamp(CFG["snapshots"]["last"]) + pd.Timedelta(days=H) <= pd.Timestamp("2011-12-09")    # no incomplete follow-up labelled as churn
    assert pd.Timestamp(CFG["snapshots"]["first"]) - pd.Timedelta(days=CFG["task"]["lookback_days"]) >= pd.Timestamp("2009-12-01")

def test_forward_chain_folds_purge_and_never_leak_forward():
    snaps = pd.date_range("2010-06-01", "2010-12-01", freq="MS"); df = pd.DataFrame({"snapshot": np.repeat(snaps, 5)}); mask = pd.Series(True, index=df.index)
    for tr, va in forward_chain_folds(df, mask, 3):
        assert df.snapshot.iloc[tr].max() + pd.DateOffset(months=3) <= df.snapshot.iloc[va].min()

def test_pipeline_preprocessing_is_fitted_on_training_rows_only():
    rng = np.random.default_rng(0); Xtr = pd.DataFrame(rng.integers(1, 50, (200, len(D.FEATURES))).astype(float), columns=D.FEATURES); Xtr.loc[:20, "mean_gap_days"] = np.nan
    ytr = rng.integers(0, 2, 200); p = make_pipeline("logreg", 1, C=1.0).fit(Xtr, ytr)
    assert np.allclose(p["impute"].statistics_, np.nanmedian(Xtr.values, axis=0))
    Xte = Xtr.copy() * 1000; before = p["impute"].statistics_.copy(); p.predict_proba(Xte); assert np.allclose(before, p["impute"].statistics_)

def test_fairness_metrics_on_known_counts():
    y = np.array([1, 1, 0, 0] * 50 + [1, 0] * 60); g = np.array(["UK"] * 200 + ["Non-UK"] * 120); pred = np.array([1, 0, 1, 0] * 50 + [1, 1] * 60)
    a = F.assess(y, pred, g, ref="UK", n_boot=20, min_n=50); t = a["table"]; c = a["comparisons"]["Non-UK"]
    assert t.loc["UK", "selection_rate"] == 0.5 and t.loc["Non-UK", "selection_rate"] == 1.0 and t.loc["UK", "tpr"] == 0.5 and t.loc["Non-UK", "fpr"] == 1.0
    assert c["disparate_impact_ratio"] == 2.0 and c["demographic_parity_difference"] == 0.5 and c["equalized_odds_difference"] == 0.5 and not c["all_checks_pass"]

# ---------------------------------------------------------------- serialisation and API
def test_serialised_model_loads_and_matches_metadata():
    p = next(ROOT.glob("models/churn_*_v*.joblib")); meta = json.loads(p.with_suffix(".metadata.json").read_text()); pipe = joblib.load(p)
    assert meta["feature_order"] == D.FEATURES and 0 < meta["threshold"] < 1 and list(pipe[:-1].get_feature_names_out())
    pr = pipe.predict_proba(pd.DataFrame([VALID | {"is_single_invoice": 0}])[D.FEATURES].astype(float))[0, 1]; assert 0 < pr < 1

client = TestClient(app)
def test_api_valid_request_returns_probability_flag_threshold_and_version():
    r = client.post("/predict", json=VALID); b = r.json(); assert r.status_code == 200
    assert set(b) == {"request_id", "model_version", "churn_probability", "flagged_high_churn_risk", "decision_threshold", "imputed_fields", "notes"}
    assert b["decision_threshold"] == THRESHOLD and b["flagged_high_churn_risk"] == (b["churn_probability"] >= THRESHOLD) and b["model_version"] == "1.0.0"

def test_api_matches_pipeline_directly():
    pipe = joblib.load(next(ROOT.glob("models/churn_*_v*.joblib"))); row = pd.DataFrame([VALID | {"is_single_invoice": 0}])[API_FEATURES].astype(float)
    assert abs(client.post("/predict", json=VALID).json()["churn_probability"] - float(pipe.predict_proba(row)[0, 1])) < 1e-6

def test_api_missing_gap_fields_are_imputed_and_reported():
    r = client.post("/predict", json=VALID | {"mean_gap_days": None, "std_gap_days": None, "recency_over_gap": None}).json()
    assert set(r["imputed_fields"]) == {"mean_gap_days", "std_gap_days", "recency_over_gap"}

@pytest.mark.parametrize("patch", [{"recency_days": -1}, {"recency_days": 500}, {"n_inv_30": 9}, {"rev_90": 99999}, {"cancel_ratio": 1.5}, {"n_inv_all": 0}, {"tenure_days": 10},
                                   {"is_single_invoice": 1}, {"customer_id": "abc"}, {"n_inv_all": "many"}, {"n_inv_90": 0, "n_inv_prev90": 0, "n_inv_30": 0}])
def test_api_rejects_invalid_inputs_without_echoing_values(patch):
    r = client.post("/predict", json=VALID | patch); assert r.status_code == 422
    assert "many" not in r.text and "abc" not in r.text

def test_api_rejects_missing_required_field_and_empty_body():
    assert client.post("/predict", json={k: v for k, v in VALID.items() if k != "rev_all"}).status_code == 422 and client.post("/predict", json={}).status_code == 422

def test_api_does_not_log_request_bodies(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="churn_api"): client.post("/predict", json=VALID | {"rev_all": 1234567.891})
    assert "1234567" not in caplog.text and "request_id=" in caplog.text

def test_api_health_and_model_info():
    assert client.get("/health").json()["status"] == "ok"; m = client.get("/model").json(); assert m["model_version"] == "1.0.0" and "not_for" in m

@pytest.mark.skipif(not (ROOT / "data" / "modeling" / "test_predictions.parquet").exists(), reason="modelling table not present (git-ignored)")
def test_api_reproduces_stored_test_predictions_on_sample():
    df = pd.read_parquet(ROOT / "data" / "modeling" / "churn_snapshots.parquet"); te = df[D.split_masks(df, CFG)["test"]].reset_index(drop=True)
    pr = pd.read_parquet(ROOT / "data" / "modeling" / "test_predictions.parquet"); idx = np.random.default_rng(0).choice(len(te), 25, replace=False)
    for i in idx:
        body = {k: (None if pd.isna(te.loc[i, k]) else float(te.loc[i, k])) for k in D.FEATURES if k != "is_single_invoice"}
        for k in ("n_inv_all", "n_inv_30", "n_inv_90", "n_inv_prev90", "n_products_all", "n_products_180", "n_cancel_all"): body[k] = int(body[k])
        r = client.post("/predict", json=body); assert r.status_code == 200, r.text
        assert abs(r.json()["churn_probability"] - pr.p.iloc[i]) < 1e-5 and r.json()["flagged_high_churn_risk"] == bool(pr.pred.iloc[i])
