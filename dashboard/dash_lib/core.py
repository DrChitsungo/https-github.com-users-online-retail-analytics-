"""Pure helpers for the Module 5 dashboard (no Streamlit import, so they are unit-tested).

- metrics_from_counts: recompute precision/recall/etc. from confusion counts; returns None where the denominator is zero (undefined, never 0).
- apply_scenario: copy of churn_model.explain.apply_scenario (Module 4 counterfactual method); tests assert the two give identical results.
- ApiClient: thin client for the Module 4 FastAPI service. Errors are returned, never swallowed, and no score is ever invented.
"""
from __future__ import annotations
import json, os
from pathlib import Path
import requests

DATA = Path(__file__).resolve().parents[1] / "data" / "dashboard_evidence.json"
MIN_N = 100   # configs/churn.yaml fairness.min_group_n

LABELS = {"recency_days": "Days since last purchase", "tenure_days": "Days since first purchase", "n_inv_all": "Invoices (all history)", "n_inv_30": "Invoices, last 30 days",
          "n_inv_90": "Invoices, last 90 days", "n_inv_prev90": "Invoices, 91-180 days ago", "is_single_invoice": "Only one purchase so far", "rev_all": "Revenue, all history (GBP)",
          "rev_90": "Revenue, last 90 days (GBP)", "rev_180": "Revenue, last 180 days (GBP)", "n_products_all": "Distinct products (all)", "n_products_180": "Distinct products, 180 days",
          "avg_units_per_inv": "Average units per invoice", "mean_gap_days": "Mean days between purchases", "std_gap_days": "Spread of days between purchases",
          "recency_over_gap": "Recency / mean gap", "n_cancel_all": "Cancellation invoices", "cancel_ratio": "Cancellation share"}


def load_evidence(path: Path = DATA) -> dict:
    return json.loads(Path(path).read_text())


def _ratio(a, b):
    return None if not b else a / b


def metrics_from_counts(c: dict) -> dict:
    tp, fp, fn, tn, n = c["tp"], c["fp"], c["fn"], c["tn"], c["n"]
    prec, rec = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = None if prec is None or rec is None or (prec + rec) == 0 else 2 * prec * rec / (prec + rec)
    return {"n": n, "prevalence": _ratio(tp + fn, n), "flag_rate": _ratio(tp + fp, n), "precision": prec, "recall": rec, "f1": f1, "accuracy": _ratio(tp + tn, n),
            "fpr": _ratio(fp, fp + tn), "auc": c.get("auc"), "small_sample": n < MIN_N}


def fmt_pct(x, d=1):
    return "undefined" if x is None else f"{100 * x:.{d}f}%"


def apply_scenario(row: dict, k: int, r: int) -> dict:
    """k extra sales invoices at the customer's own average invoice value, the latest r days before the prediction date. Identical logic to Module 4."""
    x = dict(row)
    if k == 0:
        return x
    add = k * (row["rev_all"] / row["n_inv_all"])
    x["recency_days"] = min(row["recency_days"], r)
    for col in ("n_inv_90", "n_inv_all"):
        x[col] = row[col] + k
    x["is_single_invoice"] = 0
    if r <= 30:
        x["n_inv_30"] = row["n_inv_30"] + k
    for col in ("rev_90", "rev_180", "rev_all"):
        x[col] = row[col] + add
    mg = row.get("mean_gap_days")
    x["recency_over_gap"] = x["recency_days"] / mg if (mg is not None and mg == mg and mg > 0) else row["recency_over_gap"]
    return x


def to_payload(profile: dict) -> dict:
    """API request body: model-ready features only (no identifiers). Integer fields are cast; NaN/None gap fields are sent as null."""
    ints = ("n_inv_all", "n_inv_30", "n_inv_90", "n_inv_prev90", "n_products_all", "n_products_180", "n_cancel_all", "is_single_invoice")
    out = {}
    for k, v in profile.items():
        out[k] = None if v is None or v != v else (int(round(v)) if k in ints else float(v))
    return out


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 6.0):
        self.base = (base_url or os.environ.get("CHURN_API_URL", "http://127.0.0.1:8000")).rstrip("/"); self.timeout = timeout

    def _call(self, method, path, **kw):
        try:
            r = requests.request(method, self.base + path, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            return {"ok": False, "status": None, "error": f"Cannot reach the model API at {self.base} ({type(e).__name__}). No score was produced."}
        try:
            body = r.json()
        except ValueError:
            return {"ok": False, "status": r.status_code, "error": f"The model API returned a non-JSON response (HTTP {r.status_code})."}
        return {"ok": r.status_code == 200, "status": r.status_code, "body": body, "request_id": r.headers.get("X-Request-ID")}

    def health(self): return self._call("GET", "/health")
    def model(self): return self._call("GET", "/model")
    def predict(self, payload: dict): return self._call("POST", "/predict", json=payload)
