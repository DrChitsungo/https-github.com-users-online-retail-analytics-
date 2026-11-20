"""Batch monitoring (capstone Section 7): PSI behaves as expected and the committed summary is aggregate-only and complete."""
import json
import numpy as np, pytest
pytest.importorskip("sklearn"); pytest.importorskip("joblib")
from churn_model import monitoring as mon

SUMMARY = mon.ROOT / "reports" / "monitoring" / "monitoring_summary.json"


def test_psi_is_zero_for_identical_and_large_for_shifted():
    rng = np.random.default_rng(0); a = rng.normal(size=5000)
    assert mon.psi(a, a) < 1e-6
    assert mon.psi(a, rng.normal(size=5000)) < 0.05
    assert mon.psi(a, rng.normal(loc=1.0, size=5000)) > 0.2


def test_psi_handles_missing_and_constant_inputs():
    a = np.array([0.0] * 900 + [1.0] * 100); b = np.array([0.0] * 500 + [1.0] * 500)
    assert mon.psi(a, b) > 0.2
    assert np.isfinite(mon.psi(np.array([1.0, np.nan, 2.0, 3.0] * 50), np.array([np.nan] * 200)))


@pytest.mark.skipif(not SUMMARY.exists(), reason="monitoring summary not generated")
def test_committed_summary_is_aggregate_and_complete():
    text = SUMMARY.read_text(); s = json.loads(text)
    assert "customer_key" not in text and "customer_id" not in text.lower()
    assert s["model_version"] == mon.META["model_version"] and abs(s["threshold"] - mon.THRESHOLD) < 1e-12
    assert [m["month"] for m in s["months"]] == ["2011-05", "2011-06", "2011-07", "2011-08", "2011-09"]
    for m in s["months"]:
        assert set(m["input_psi"]) == set(mon.FEATURES)
        assert m["status"] == ("ALERT" if m["alerts"] else "OK")
        assert m["fairness"]["sufficient_n"]


@pytest.mark.skipif(not SUMMARY.exists(), reason="monitoring summary not generated")
def test_test_months_match_recorded_test_evaluation():
    """Aug and Sep 2011 together are the held-out test set: their pooled counts must reproduce the recorded test recall."""
    s = json.loads(SUMMARY.read_text()); rec = json.loads((mon.ROOT / "reports/model/final_test_results.json").read_text())
    ms = [m for m in s["months"] if m["used_for"] == "test"]
    assert sum(m["n"] for m in ms) == rec["test_rows"]
    pooled_recall = sum(m["recall"] * m["n"] * m["prevalence"] for m in ms) / sum(m["n"] * m["prevalence"] for m in ms)
    assert abs(pooled_recall - rec["models"]["logreg"]["test"]["recall"]) < 1e-3
