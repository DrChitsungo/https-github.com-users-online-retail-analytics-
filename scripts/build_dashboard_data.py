"""Build the aggregate-only evidence file used by the public Module 5 dashboard.

Reads the recorded Module 4 outputs (reports/model/*.json, models/*.metadata.json) and, for the filter grid and the calibration table, the git-ignored
test predictions. Writes dashboard/data/dashboard_evidence.json. Nothing is retrained and nothing is invented: every number is copied or recomputed
from those files. The output contains NO customer keys, row indexes or dates of individual customers; the five example profiles are rounded behavioural
aggregates labelled A-E. Run: PYTHONPATH=src python scripts/build_dashboard_data.py"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = Path(__file__).resolve().parents[1]; R = ROOT / "reports" / "model"; OUT = ROOT / "dashboard" / "data" / "dashboard_evidence.json"
J = lambda p: json.loads((ROOT / p).read_text())
sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()[:16]

meta = J("models/churn_logreg_v1.0.0.metadata.json"); fin = J("reports/model/final_test_results.json"); exp = J("reports/model/explainability_results.json")
mit = J("reports/model/mitigation_results.json"); abl = J("reports/model/ablation_country_flag.json"); cfg = json.loads(json.dumps(__import__("yaml").safe_load((ROOT / "configs/churn.yaml").read_text()), default=str))
tp = pd.read_parquet(ROOT / "data/modeling/test_predictions.parquet"); thr = meta["threshold"]
assert abs(thr - fin["threshold"]) < 1e-9 and len(tp) == fin["test_rows"]

def counts(d):
    y, pr = d.churn.values, d.pred.values
    c = dict(n=int(len(d)), tp=int(((y == 1) & (pr == 1)).sum()), fp=int(((y == 0) & (pr == 1)).sum()), fn=int(((y == 1) & (pr == 0)).sum()), tn=int(((y == 0) & (pr == 0)).sum()))
    c["auc"] = float(roc_auc_score(y, d.p)) if 0 < y.sum() < len(y) else None
    c["brier"] = float(brier_score_loss(y, d.p)) if len(d) else None
    return c

tp["month"] = pd.to_datetime(tp.snapshot).dt.strftime("%Y-%m"); tp["grp"] = np.where(tp.group_uk.astype(str).str.upper().str.startswith("UK"), "UK", "Non-UK")
grid = {}
for mo in ["All"] + sorted(tp.month.unique()):
    for g in ["All", "UK", "Non-UK"]:
        d = tp if mo == "All" else tp[tp.month == mo]; d = d if g == "All" else d[d.grp == g]; grid[f"{mo}|{g}"] = counts(d)
assert grid["All|All"]["tp"] == fin["models"]["logreg"]["test"]["tp"], "filter grid must reproduce the recorded confusion matrix"

q = pd.qcut(tp.p.rank(method="first"), 10, labels=False)
calib = [{"decile": int(i) + 1, "n": int((q == i).sum()), "mean_score": float(tp.p[q == i].mean()), "observed_churn": float(tp.churn[q == i].mean())} for i in range(10)]
bins = np.linspace(0, 1, 21); hist = {"bin_edges": bins.round(2).tolist(),
    "churned": np.histogram(tp.p[tp.churn == 1], bins)[0].tolist(), "retained": np.histogram(tp.p[tp.churn == 0], bins)[0].tolist()}

# five held-out example cases: rounded behavioural aggregates, no identifiers, no dates
import sys; sys.path.insert(0, str(ROOT / "src"))
from churn_model import dataset as D, tracking
cfgm = tracking.cfg(); df = pd.read_parquet(ROOT / "data/modeling/churn_snapshots.parquet"); te = df[D.split_masks(df, cfgm)["test"]].reset_index(drop=True)
assert len(te) == len(tp)
NICE = {"A_typical_true_positive": "Case A: typical flagged churner", "B_typical_true_negative": "Case B: typical retained customer", "C_confident_false_positive": "Case C: most confident false alarm",
        "D_missed_churner_false_negative": "Case D: missed churner", "E_borderline": "Case E: borderline, nearest the threshold"}
def rnd(row):
    out = {}
    for f in D.FEATURES:
        v = row[f]; out[f] = None if pd.isna(v) else (int(v) if f.startswith("n_") and f != "n_products_all" or f in ("is_single_invoice",) else float(round(v, 2)))
    for f in ("rev_all", "rev_90", "rev_180"): out[f] = float(round(row[f] / 5) * 5)       # nearest GBP 5
    for f in ("recency_days", "tenure_days", "mean_gap_days", "std_gap_days"):
        if out[f] is not None: out[f] = float(round(out[f]))
    for f in ("n_products_all", "n_products_180"): out[f] = int(row[f])
    for f in ("avg_units_per_inv",): out[f] = float(round(row[f]))
    return out
cases = {}
for k, c in exp["local"].items():
    row = te.iloc[c["row"]]; stored_p = float(tp.p.iloc[c["row"]]); assert abs(stored_p - c["p_churn"]) < 1e-9
    cases[k] = {"label": NICE[k], "stored_score": c["p_churn"], "actual_churn": c["actual_churn"], "flagged": c["flagged"], "top_drivers": c["top_drivers"], "profile": rnd(row)}

fa = fin["fairness"]
out = {
    "meta": {"model_name": meta["model_name"], "model_version": meta["model_version"], "task": meta["task"], "threshold": thr, "dataset_hash": meta["dataset_hash"],
             "model_sha256_16": sha("models/churn_logreg_v1.0.0.joblib"), "test_window": "prediction dates 2011-08-01 and 2011-09-01 (90-day outcome windows complete)",
             "test_rows": fin["test_rows"], "test_customers": fin["test_customers"], "prevalence": fin["test_prevalence"], "mean_score": fin["mean_predicted_probability"],
             "splits": cfg["split"], "horizon_days": cfg["task"]["horizon_days"], "lookback_days": cfg["task"]["lookback_days"], "features": D.FEATURES,
             "intended_use": meta["intended_use"], "not_for": meta["not_for"], "mlflow": meta["mlflow"], "registry": meta.get("registry"),
             "sources": {p: sha(p) for p in ["reports/model/final_test_results.json", "reports/model/explainability_results.json", "reports/model/mitigation_results.json", "models/churn_logreg_v1.0.0.metadata.json"]}},
    "headline": {"logreg": fin["models"]["logreg"]["test"], "logreg_ci": fin["models"]["logreg"]["ci"], "baseline_recency_rule": fin["models"]["baseline_recency_rule"]["test"],
                 "baseline_prevalence": fin["models"]["baseline_prevalence"]["test"], "lightgbm_auc": fin["models"]["lightgbm"]["test"]["roc_auc"], "random_forest_auc": fin["models"]["random_forest"]["test"]["roc_auc"],
                 "validation_auc": meta["validation"]["roc_auc"]},
    "operating_points": fin["operating_points"], "subsets": {k: {kk: v[kk] for kk in ("n", "prevalence", "recall", "precision", "roc_auc")} for k, v in fin["subsets"].items()},
    "filter_grid": grid, "calibration_deciles": calib, "score_histogram": hist,
    "global_shap": {"group_importance": exp["global_shap"]["group_importance"], "mean_abs_shap_top": dict(list(exp["global_shap"]["mean_abs_shap"].items())[:10]),
                    "direction_spearman": exp["global_shap"]["direction_spearman"], "scale": exp["global_shap"]["output_scale"], "explained_rows": exp["global_shap"]["explained_rows"],
                    "agreement_with_lightgbm": exp["shap_model_agreement"]},
    "cases": cases, "case_rule": exp["case_selection_rule"], "counterfactuals": {"batch": exp["counterfactuals"]["batch"], "cases": {k: {kk: v.get(kk) for kk in ("extra_invoices", "latest_purchase_days_before_T", "p0", "p1", "found")} for k, v in exp["counterfactuals"]["cases"].items()},
                                                                                  "immutable": exp["counterfactuals"]["immutable"]},
    "sensitivity": exp["sensitivity"],
    "fairness": {"grouping": "UK vs non-UK customers (operational grouping, NOT a protected attribute)", "overall": fa["overall"], "table": fa["table"], "comparisons": fa["comparisons"], "brier_by_group": fa["brier_by_group"],
                 "per_country": fa["per_country"], "min_group_n": cfg["fairness"]["min_group_n"], "relative_band": cfg["fairness"]["relative_band"], "di_band": cfg["fairness"]["disparate_impact_band"],
                 "mitigation": {k: {"validation": v["validation"], "test_exploratory": v["test_exploratory"], "note": v.get("note")} for k, v in mit.items() if isinstance(v, dict) and "validation" in v},
                 "country_flag_ablation": abl},
}
assert "customer_key" not in json.dumps(out)
def clean(o):   # strict JSON: undefined rates (zero denominators) become null, never NaN
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    return None if isinstance(o, float) and o != o else o
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(clean(out), indent=1, default=float, allow_nan=False)); print("wrote", OUT, OUT.stat().st_size, "bytes")
