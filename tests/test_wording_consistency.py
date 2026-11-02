"""The protected-attribute statement and the agreed churn definition must read the same everywhere they appear (reports, Model Card, notebook, API docs, registry evidence)."""
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
STATEMENT = "are not present in Online Retail II and were not inferred. Therefore a formal protected-attribute fairness analysis is not possible on this dataset. Requirement recorded as unmet due to data limitation."
DEFINITION = "churn = no sales invoice (purchase) in the 90 days following the observation date, with the customer eligible only if they had at least 180 days of prior history (first sales invoice at least 180 days before the observation date)."


def _need(*paths):
    # The Docker CI image copies only src, configs, docs, scripts and tests; documents elsewhere are checked in the other CI jobs and locally.
    missing = [p for p in paths if not (ROOT / p).exists()]
    if missing: pytest.skip(f"not present in this checkout/image: {missing}")


def _t(p): return " ".join((ROOT / p).read_text().split())


def test_protected_attribute_statement_in_all_documents():
    _need("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md", "reports/Model_Validation_Report.md")
    for p in ("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md", "reports/Model_Validation_Report.md"):
        assert STATEMENT in _t(p), p


def test_churn_definition_consistent_and_labelled_agreed():
    _need("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md", "reports/Model_Validation_Report.md", "notebooks/shap_analysis.ipynb", "reports/mlflow_evidence/model_registry.json")
    for p in ("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md", "reports/Model_Validation_Report.md"):
        assert DEFINITION in _t(p) and "agreed" in _t(p) and "1 November 2026" in _t(p), p
    nb = json.loads((ROOT / "notebooks/shap_analysis.ipynb").read_text()); assert DEFINITION in " ".join("".join(c["source"]) for c in nb["cells"])
    assert "no sales invoice in the 90 days following the observation date" in (ROOT / "src/churn_model/api.py").read_text()
    reg = json.loads((ROOT / "reports/mlflow_evidence/model_registry.json").read_text()); assert "1 November 2026" in reg["tags"]["churn_definition"] and "PROPOSED" not in reg["tags"]["churn_definition"]


def test_grouping_labels_and_no_synthetic_attribute():
    _need("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md", "reports/model/segment_audit.json")
    for p in ("docs/MODEL_CARD.md", "reports/Fairness_Metrics_Report.md"):
        t = _t(p); assert "geographic_grouping_for_robustness_check" in t and "customer-segment audit" in t
    assert "synthetic" not in json.dumps(json.loads((ROOT / "reports/model/segment_audit.json").read_text())).lower()


def test_segment_audit_is_aggregate_only_and_complete():
    _need("reports/model/segment_audit.json")
    a = json.loads((ROOT / "reports/model/segment_audit.json").read_text()); s = json.dumps(a)
    assert "customer_key" not in s and set(a["dimensions"]) == {"tenure_tier", "spend_tier", "frequency_tier"}
    for d in a["dimensions"].values(): assert sum(r["n"] for r in d["tiers"].values()) == json.loads((ROOT / "reports/model/final_test_results.json").read_text())["test_rows"]
