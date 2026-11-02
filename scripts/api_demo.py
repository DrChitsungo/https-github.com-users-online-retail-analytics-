"""API demonstration for the Module 4 churn model (Module 5). Standard library only; no secrets; sends model-ready features, never identifiers.

  # terminal 1 (from the repository root)
  PYTHONPATH=src uvicorn churn_model.api:app --port 8000
  # terminal 2
  python scripts/api_demo.py                                  # runs against http://127.0.0.1:8000
  python scripts/api_demo.py --base-url http://host:8000 --check-parity --out reports/evidence/api_demo_output.txt

Steps: health, model info, a valid request, a scenario request, an invalid request (422, values never echoed), an unknown-field request (422), and
optionally a parity check of the API against the serialised model loaded directly. Exit code 1 if any expectation fails."""
from __future__ import annotations
import argparse, json, sys, urllib.error, urllib.request
from pathlib import Path

VALID = {"recency_days": 40, "tenure_days": 400, "n_inv_all": 6, "n_inv_30": 0, "n_inv_90": 1, "n_inv_prev90": 2, "rev_all": 1800.5, "rev_90": 300, "rev_180": 900,
         "n_products_all": 60, "n_products_180": 35, "avg_units_per_inv": 120, "mean_gap_days": 55, "std_gap_days": 20, "recency_over_gap": 0.73, "n_cancel_all": 0, "cancel_ratio": 0}
LOG = []

def say(s=""):
    print(s); LOG.append(s)

def call(base, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
    except urllib.error.URLError as e:
        say(f"Cannot reach {base}: {e.reason}. Start the API first (see the docstring of this script)."); sys.exit(2)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--base-url", default="http://127.0.0.1:8000"); ap.add_argument("--check-parity", action="store_true"); ap.add_argument("--out"); a = ap.parse_args()
    base = a.base_url.rstrip("/"); ok = True
    def expect(label, cond):
        nonlocal ok; ok &= bool(cond); say(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    say(f"API demonstration against {base}\n")
    say("1. GET /health"); s, b = call(base, "GET", "/health"); say(json.dumps(b)); expect("status 200 and model_version present", s == 200 and "model_version" in b); version = b.get("model_version")
    say("\n2. GET /model (selected fields)"); s, b = call(base, "GET", "/model")
    say(json.dumps({k: b[k] for k in ("model_version", "task", "threshold")} | {"test_roc_auc": round(b["test"]["roc_auc"], 3), "intended_use": b["intended_use"]}, indent=1)); expect("model info matches health version", b["model_version"] == version)
    say("\n3. POST /predict with a valid request"); say("request:  " + json.dumps(VALID)); s, b = call(base, "POST", "/predict", VALID); say("response: " + json.dumps(b, indent=1))
    expect("200, probability in (0,1), flag consistent with threshold", s == 200 and 0 < b["churn_probability"] < 1 and b["flagged_high_churn_risk"] == (b["churn_probability"] >= b["decision_threshold"]))
    p0 = b["churn_probability"]
    say("\n4. Scenario: the same customer with three more invoices (recomputed consistently), latest purchase 30 days before the prediction date")
    sc = VALID | {"n_inv_all": 9, "n_inv_90": 4, "n_inv_30": 3, "recency_days": 30, "rev_all": 1800.5 + 3 * 1800.5 / 6, "rev_90": 300 + 3 * 1800.5 / 6, "rev_180": 900 + 3 * 1800.5 / 6, "recency_over_gap": 30 / 55}
    s, b = call(base, "POST", "/predict", sc); say(f"risk score {p0:.4f} -> {b.get('churn_probability')}  (a model-sensitivity illustration, not a causal effect)"); expect("scenario accepted", s == 200)
    say("\n5. POST /predict with an invalid request (tenure below the 180-day eligibility minimum)"); s, b = call(base, "POST", "/predict", VALID | {"tenure_days": 5, "recency_days": 100}); say(f"HTTP {s}: " + json.dumps(b))
    expect("422 and submitted values are not echoed", s == 422 and "100" not in json.dumps(b).replace("le=100000", "") and b["detail"] == "invalid input")
    say("\n6. POST /predict with an unknown field (e.g. an identifier)"); s, b = call(base, "POST", "/predict", VALID | {"customer_id": "C-123"}); say(f"HTTP {s}: " + json.dumps(b)); expect("422: identifiers are refused", s == 422 and "C-123" not in json.dumps(b))
    if a.check_parity:
        say("\n7. Parity of the API with the serialised model loaded directly")
        try:
            import joblib, pandas as pd
            root = Path(__file__).resolve().parents[1]; pipe = joblib.load(next(root.glob("models/churn_*_v*.joblib"))); meta = json.loads(next(root.glob("models/churn_*_v*.metadata.json")).read_text())
            row = pd.DataFrame([VALID | {"is_single_invoice": 0}])[meta["feature_order"]].astype(float); direct = float(pipe.predict_proba(row)[0, 1])
            say(f"direct {direct:.6f} vs API {p0:.6f}"); expect("equal to 6 decimals", abs(direct - p0) < 1e-6)
        except Exception as e: say(f"  [SKIP] parity check needs joblib, pandas, scikit-learn and the model file: {type(e).__name__}")
    say("\nRESULT: " + ("ALL EXPECTATIONS MET" if ok else "SOME EXPECTATIONS FAILED"))
    if a.out: Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text("\n".join(LOG) + "\n")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
