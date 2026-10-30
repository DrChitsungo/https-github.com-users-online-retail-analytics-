"""Explainability for the selected churn model: global/local SHAP, constrained counterfactuals, sensitivity analysis.
All outputs are produced from the fitted pipeline and the real test/train rows. SHAP values are on the LOG-ODDS (margin) scale.
Run: PYTHONPATH=src python -m churn_model.explain"""
from __future__ import annotations
import json
import joblib, numpy as np, pandas as pd, shap
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from . import dataset as D, tracking

ROOT = tracking.ROOT; FIG = ROOT / "reports" / "model" / "figures"; SEED = 20261026
LABELS = {"recency_days": "Days since last purchase", "tenure_days": "Days since first purchase", "n_inv_all": "Invoices (all history)", "n_inv_30": "Invoices, last 30d",
          "n_inv_90": "Invoices, last 90d", "n_inv_prev90": "Invoices, 91-180d ago", "is_single_invoice": "Only one purchase so far", "rev_all": "Revenue (all history)", "rev_90": "Revenue, last 90d",
          "rev_180": "Revenue, last 180d", "n_products_all": "Distinct products (all)", "n_products_180": "Distinct products, 180d",
          "avg_units_per_inv": "Avg units per invoice", "mean_gap_days": "Mean days between purchases", "std_gap_days": "Std of days between purchases",
          "recency_over_gap": "Recency / mean gap", "n_cancel_all": "Cancellation invoices", "cancel_ratio": "Cancellation share"}


def load():
    c = tracking.cfg(); sel = json.loads((ROOT / "reports" / "model" / "selection.json").read_text())
    s1 = json.loads((ROOT / "reports" / "model" / "stage1_validation_results.json").read_text())
    pipe = joblib.load(ROOT / "models" / "candidates" / f"{sel['final_model']}.joblib"); thr = s1["results"][sel["final_model"]]["threshold"]
    df = pd.read_parquet(ROOT / "data" / "modeling" / "churn_snapshots.parquet"); m = D.split_masks(df, c)
    names = [LABELS.get(n, n.replace("missingindicator_", "Missing: ")) if not n.startswith("missingindicator_") else "Missing: " + LABELS.get(n.replace("missingindicator_", ""), n) for n in pipe[:-1].get_feature_names_out()]
    return c, pipe, thr, df, m, names


GROUPS = {"Purchase frequency": ["Invoices (all history)", "Invoices, last 30d", "Invoices, last 90d", "Invoices, 91-180d ago", "Only one purchase so far"],
          "Recency": ["Days since last purchase", "Recency / mean gap"], "Spend": ["Revenue (all history)", "Revenue, last 90d", "Revenue, last 180d"],
          "Tenure": ["Days since first purchase"], "Product breadth": ["Distinct products (all)", "Distinct products, 180d", "Avg units per invoice"],
          "Purchase regularity": ["Mean days between purchases", "Std of days between purchases"], "Cancellations": ["Cancellation invoices", "Cancellation share"]}


def global_shap(pipe, thr, df, m, names, n_bg=500, n_explain=2000):
    rng = np.random.default_rng(SEED); tr = df[m["train"]]; te = df[m["test"]].reset_index(drop=True)
    bg = pipe[:-1].transform(tr[D.FEATURES].iloc[rng.choice(len(tr), n_bg, replace=False)])
    idx = rng.choice(len(te), n_explain, replace=False); Xs = pipe[:-1].transform(te[D.FEATURES].iloc[idx])
    ex = shap.LinearExplainer(pipe[-1], shap.maskers.Independent(bg, max_samples=n_bg)); sv = ex.shap_values(Xs)
    imp = pd.Series(np.abs(sv).mean(0), index=names).sort_values(ascending=False)
    # direction: correlation between raw (imputed, original-scale) feature value and its SHAP
    raw = pd.DataFrame(pipe[:1].transform(te[D.FEATURES].iloc[idx]), columns=names)
    direction = {n: float(spearmanr(raw[n], sv[:, i])[0]) for i, n in enumerate(names) if raw[n].nunique() > 1}
    FIG.mkdir(parents=True, exist_ok=True)
    grp = {k: float(np.abs(sv[:, [names.index(n) for n in v]].sum(1)).mean()) for k, v in GROUPS.items()}
    assert sum(len(v) for v in GROUPS.values()) == len(names), "every model feature must belong to exactly one group"
    gs = pd.Series(grp).sort_values()
    fig, ax = plt.subplots(figsize=(6.2, 3.4)); ax.barh(gs.index, gs.values, color="#F2A541"); ax.set(xlabel="Mean |summed SHAP| per customer (log-odds)", title="Importance by behaviour group")
    fig.tight_layout(); fig.savefig(FIG / "shap_group_bar.png", dpi=130); plt.close(fig)
    top = imp.head(12)[::-1]; fig, ax = plt.subplots(figsize=(6.4, 4.2)); ax.barh(top.index, top.values, color="#1C7C7D")
    ax.set(xlabel="Mean |SHAP| (change in log-odds of churn)", title="Global importance: selected logistic regression"); fig.tight_layout(); fig.savefig(FIG / "shap_global_bar.png", dpi=130); plt.close(fig)
    plt.figure(); shap.summary_plot(sv, raw, feature_names=names, max_display=12, show=False, plot_size=(7.2, 5)); plt.title("SHAP summary (log-odds of churn)", fontsize=10)
    plt.tight_layout(); plt.savefig(FIG / "shap_summary_beeswarm.png", dpi=130, bbox_inches="tight"); plt.close()
    return {"explainer": "shap.LinearExplainer (independent masker)", "output_scale": "log-odds of churn (model margin)", "background_rows": n_bg, "background_source": "random train rows (seed fixed)",
            "explained_rows": n_explain, "explained_source": "random test rows (seed fixed)", "expected_value": float(np.ravel(ex.expected_value)[0]), "mean_abs_shap": imp.round(4).to_dict(), "group_importance": {k: round(v, 4) for k, v in sorted(grp.items(), key=lambda kv: -kv[1])},
            "direction_spearman": {k: round(v, 3) for k, v in direction.items()}}, ex, sv, idx, raw


def compare_lightgbm(df, m, names, idx):
    lg = joblib.load(ROOT / "models" / "candidates" / "lightgbm.joblib"); te = df[m["test"]].reset_index(drop=True); Xs = lg[:-1].transform(te[D.FEATURES].iloc[idx])
    sv = shap.TreeExplainer(lg[-1]).shap_values(Xs); sv = sv[1] if isinstance(sv, list) else sv
    return pd.Series(np.abs(sv).mean(0), index=names)


def pick_cases(te, thr):
    """Documented selection rule (deterministic): A typical flagged churner (TP nearest median p of TPs); B typical retained (TN nearest median p of TNs);
    C most confident false positive; D least confident false negative; E nearest to the decision threshold."""
    p = te.p.values; y = te.churn.values; pred = te.pred.values; out = {}
    def nearest(mask, target): ii = np.flatnonzero(mask); return int(ii[np.argmin(np.abs(p[ii] - target))])
    tp = (y == 1) & (pred == 1); tn = (y == 0) & (pred == 0); fp = (y == 0) & (pred == 1); fn = (y == 1) & (pred == 0)
    out["A_typical_true_positive"] = nearest(tp, np.median(p[tp])); out["B_typical_true_negative"] = nearest(tn, np.median(p[tn]))
    out["C_confident_false_positive"] = int(np.flatnonzero(fp)[np.argmax(p[fp])]); out["D_missed_churner_false_negative"] = int(np.flatnonzero(fn)[np.argmin(p[fn])])
    out["E_borderline"] = int(np.argmin(np.abs(p - thr))); return out


def local_explanations(pipe, ex, thr, te, names, cases):
    res = {}
    raw = pd.DataFrame(pipe[:1].transform(te[D.FEATURES]), columns=names)
    for tag, i in cases.items():
        x = pipe[:-1].transform(te[D.FEATURES].iloc[[i]]); sv = ex.shap_values(x)[0]
        e = shap.Explanation(values=sv, base_values=float(np.ravel(ex.expected_value)[0]), data=raw.iloc[i].values, feature_names=names)
        plt.figure(); shap.plots.waterfall(e, max_display=9, show=False); plt.title(f"{tag}: P(churn)={te.p.iloc[i]:.2f}, actual={'churn' if te.churn.iloc[i] else 'retained'}", fontsize=9)
        plt.savefig(FIG / f"shap_local_{tag}.png", dpi=120, bbox_inches="tight"); plt.close()
        order = np.argsort(-np.abs(sv))[:4]
        res[tag] = {"row": int(i), "snapshot": str(te.snapshot.iloc[i].date()), "p_churn": float(te.p.iloc[i]), "actual_churn": int(te.churn.iloc[i]), "flagged": int(te.pred.iloc[i]),
                    "top_drivers": [{"feature": names[j], "value": float(raw.iloc[i, j]), "shap_log_odds": float(sv[j])} for j in order]}
    return res

# ------------------------------------------------------------------ counterfactuals
MUTABLE = ["n_inv_30", "n_inv_90", "n_inv_all", "is_single_invoice", "rev_90", "rev_180", "rev_all", "recency_days", "recency_over_gap"]
IMMUTABLE_NOTE = "tenure, product breadth, gap statistics, cancellations, country/group are held fixed"


def apply_scenario(row: pd.Series, k: int, r: int) -> pd.Series:
    """Hypothetical history in which the customer made k extra sales invoices (at their average invoice value) with the latest on day r before T.
    Keeps count/revenue windows nested and recomputes derived ratios, so every counterfactual is a self-consistent profile."""
    x = row.copy()
    if k == 0: return x
    add = k * (row.rev_all / row.n_inv_all)            # extra invoices at the customer's own average invoice value
    x["recency_days"] = min(row.recency_days, r)
    for col in ("n_inv_90", "n_inv_all"): x[col] = row[col] + k
    x["is_single_invoice"] = 0
    if r <= 30: x["n_inv_30"] = row.n_inv_30 + k
    for col in ("rev_90", "rev_180", "rev_all"): x[col] = row[col] + add
    x["recency_over_gap"] = x.recency_days / row.mean_gap_days if (row.mean_gap_days and row.mean_gap_days == row.mean_gap_days and row.mean_gap_days > 0) else row.recency_over_gap
    return x


def counterfactual(pipe, thr, row: pd.Series, max_k=6, recs=(1, 7, 14, 30, 60, 90)):
    p0 = float(pipe.predict_proba(row[D.FEATURES].to_frame().T.astype(float))[:, 1][0])
    if p0 < thr: return {"p0": p0, "needed": False}
    best = None
    for k in range(1, max_k + 1):
        for r in sorted(recs, reverse=True):          # prefer the least demanding recency first
            x = apply_scenario(row, k, r); p1 = float(pipe.predict_proba(x[D.FEATURES].to_frame().T.astype(float))[:, 1][0])
            if p1 < thr: best = {"extra_invoices": k, "latest_purchase_days_before_T": r, "p0": p0, "p1": p1, "needed": True, "found": True,
                                 "changes": {c: [float(row[c]), float(x[c])] for c in MUTABLE if abs(row[c] - x[c]) > 1e-9}}; break
        if best: break
    return best or {"p0": p0, "needed": True, "found": False, "searched": f"up to {max_k} extra invoices, latest purchase {list(recs)} days before T"}


def counterfactual_batch(pipe, thr, te, cases, n_batch=300):
    rng = np.random.default_rng(SEED); out = {"cases": {}}
    for tag, i in cases.items(): out["cases"][tag] = counterfactual(pipe, thr, te.iloc[i])
    fl = np.flatnonzero(te.pred.values == 1); pick = rng.choice(fl, min(n_batch, len(fl)), replace=False)
    r = [counterfactual(pipe, thr, te.iloc[i]) for i in pick]; found = [x for x in r if x.get("found")]
    out["batch"] = {"n_flagged_sampled": len(r), "feasible_share": len(found) / len(r), "median_extra_invoices": float(np.median([x["extra_invoices"] for x in found])) if found else None,
                    "share_needing_1_invoice": float(np.mean([x["extra_invoices"] == 1 for x in found])) if found else None, "search_limit": "up to 6 extra invoices"}
    # verification: re-score every reported counterfactual through the fitted pipeline
    ver = 0; tot = 0
    for tag, i in cases.items():
        cf = out["cases"][tag]
        if cf.get("found"):
            tot += 1; x = apply_scenario(te.iloc[i], cf["extra_invoices"], cf["latest_purchase_days_before_T"])
            ver += int(pipe.predict_proba(x[D.FEATURES].to_frame().T.astype(float))[0, 1] < thr and abs(pipe.predict_proba(x[D.FEATURES].to_frame().T.astype(float))[0, 1] - cf["p1"]) < 1e-9)
    out["verified_reported_case_counterfactuals"] = f"{ver}/{tot}"; out["immutable"] = IMMUTABLE_NOTE
    return out

# ------------------------------------------------------------------ sensitivity
def sensitivity(pipe, thr, te, names, ex, base_sv_rank, n_rep=10):
    rng = np.random.default_rng(SEED); X0 = te[D.FEATURES].copy(); y = te.churn.values
    p0 = pipe.predict_proba(X0)[:, 1]; auc0 = roc_auc_score(y, p0); rows = []
    def record(name, X, rep=0):
        p = pipe.predict_proba(X)[:, 1]
        rows.append({"perturbation": name, "rep": rep, "auc": roc_auc_score(y, p), "delta_auc": roc_auc_score(y, p) - auc0, "mean_abs_dp": float(np.mean(np.abs(p - p0))),
                     "flag_flip_rate": float(np.mean((p >= thr) != (p0 >= thr)))})
    for s in (0.1, 0.2):
        for rep in range(n_rep):
            X = X0.copy(); f = rng.lognormal(0, s, len(X))
            for col in ("rev_all", "rev_90", "rev_180"): X[col] = X[col] * f
            record(f"monetary noise (lognormal sigma={s})", X, rep)
    for sh in (-7, -3, 3, 7):
        X = X0.copy(); X["recency_days"] = (X.recency_days + sh).clip(1, 180); X["recency_over_gap"] = X.recency_days / X.mean_gap_days.replace(0, np.nan); record(f"recency shift {sh:+d} days", X)
    for frac in (0.05, 0.10, 0.20):
        for rep in range(n_rep):
            X = X0.copy()
            for col in ("mean_gap_days", "std_gap_days", "recency_over_gap", "avg_units_per_inv", "n_products_180"):
                X.loc[rng.random(len(X)) < frac, col] = np.nan
            record(f"random missingness {int(frac*100)}% in 5 features", X, rep)
    X = X0.copy(); X["n_cancel_all"] = 0; X["cancel_ratio"] = 0; record("cancellation history unavailable", X)
    r = pd.DataFrame(rows); g = r.groupby("perturbation").agg(auc=("auc", "mean"), delta_auc=("delta_auc", "mean"), delta_auc_min=("delta_auc", "min"), mean_abs_dp=("mean_abs_dp", "mean"), flag_flip_rate=("flag_flip_rate", "mean"), reps=("rep", "count")).round(4)
    return g, auc0


def main():
    import mlflow
    c, pipe, thr, df, m, names = load(); tracking.setup()
    te = df[m["test"]].reset_index(drop=True); pr = pd.read_parquet(ROOT / "data" / "modeling" / "test_predictions.parquet")
    assert (pr.customer_key.values == te.customer_key.values).all() and (pr.snapshot.values == te.snapshot.values).all()
    te["p"] = pr.p.values; te["pred"] = pr.pred.values
    assert np.allclose(te.p.values, pipe.predict_proba(te[D.FEATURES])[:, 1]), "stored predictions must match the fitted pipeline"
    g, ex, sv, idx, raw = global_shap(pipe, thr, df, m, names)
    lg = compare_lightgbm(df, m, names, idx); lr_imp = pd.Series(g["mean_abs_shap"])
    common = [n for n in lr_imp.index if n in lg.index]
    cmp = {"spearman_rank_logreg_vs_lightgbm": float(spearmanr(lr_imp[common], lg[common])[0]), "top5_overlap": len(set(lr_imp.head(5).index) & set(lg.sort_values(ascending=False).head(5).index)),
           "logreg_top5": list(lr_imp.head(5).index), "lightgbm_top5": list(lg.sort_values(ascending=False).head(5).index)}
    cases = pick_cases(te, thr); loc = local_explanations(pipe, ex, thr, te, names, cases)
    cf = counterfactual_batch(pipe, thr, te, cases); sens, auc0 = sensitivity(pipe, thr, te, names, ex, None)
    out = {"global_shap": g, "shap_model_agreement": cmp, "case_selection_rule": pick_cases.__doc__, "local": loc, "counterfactuals": cf, "sensitivity": sens.reset_index().to_dict("records"), "baseline_test_auc": auc0, "threshold": thr}
    (ROOT / "reports" / "model" / "explainability_results.json").write_text(json.dumps(out, indent=2, default=float))
    with mlflow.start_run(run_name="explainability-final-model"):
        mlflow.set_tags({"iteration": tracking.ITERATION, "stage": "explainability", "model_kind": "selected", "output_scale": "log-odds"})
        mlflow.log_params({"model": "logreg", "shap_background_rows": 500, "shap_explained_rows": 2000, "seed": SEED})
        mlflow.log_metrics({"shap_rank_spearman_vs_lightgbm": cmp["spearman_rank_logreg_vs_lightgbm"], "cf_feasible_share": cf["batch"]["feasible_share"]})
        mlflow.log_artifact(str(ROOT / "reports" / "model" / "explainability_results.json"))
        for f in FIG.glob("shap_*.png"): mlflow.log_artifact(str(f), artifact_path="figures")
    print(json.dumps({"top": dict(list(g["mean_abs_shap"].items())[:8]), "dir": {k: g["direction_spearman"].get(k) for k in list(g["mean_abs_shap"])[:8]}}, indent=1))
    print(cmp); print({t: (round(v["p_churn"], 3), v["actual_churn"]) for t, v in loc.items()}); print(json.dumps(cf["batch"]), cf["verified_reported_case_counterfactuals"])
    print({t: (v.get("found"), v.get("extra_invoices"), v.get("latest_purchase_days_before_T")) for t, v in cf["cases"].items()}); print(sens.to_string())

if __name__ == "__main__":
    main()
