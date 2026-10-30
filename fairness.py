"""Group performance and fairness metrics for a binary churn flag.
Definitions (Module 2 s6.2): positive prediction = customer FLAGGED as high churn risk = selected for a retention offer.
Favourable outcome is therefore 'flagged'. Grouping = UK vs Non-UK customers (operational grouping, NOT a protected attribute).
"""
from __future__ import annotations
import numpy as np, pandas as pd
from scipy.stats import norm


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def group_table(y, pred, groups, min_n=100) -> pd.DataFrame:
    y = np.asarray(y); pred = np.asarray(pred); rows = []
    for g in pd.unique(groups):
        m = np.asarray(groups) == g; yy, pp = y[m], pred[m]
        tp = int(((yy == 1) & (pp == 1)).sum()); fp = int(((yy == 0) & (pp == 1)).sum()); fn = int(((yy == 1) & (pp == 0)).sum()); tn = int(((yy == 0) & (pp == 0)).sum())
        n = int(m.sum()); pos = tp + fn; neg = fp + tn
        r = {"group": g, "n": n, "prevalence": yy.mean(), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "selection_rate": pp.mean(),
             "tpr": tp / pos if pos else np.nan, "fpr": fp / neg if neg else np.nan, "precision": tp / (tp + fp) if (tp + fp) else np.nan,
             "accuracy": (tp + tn) / n, "sufficient_n": n >= min_n and pos >= 30 and neg >= 30}
        r["sel_lo"], r["sel_hi"] = wilson(int(pp.sum()), n); r["tpr_lo"], r["tpr_hi"] = wilson(tp, pos); r["fpr_lo"], r["fpr_hi"] = wilson(fp, neg)
        rows.append(r)
    return pd.DataFrame(rows).set_index("group")


def overall(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    return {"selection_rate": pred.mean(), "tpr": ((y == 1) & (pred == 1)).sum() / max((y == 1).sum(), 1), "fpr": ((y == 0) & (pred == 1)).sum() / max((y == 0).sum(), 1)}


def assess(y, pred, groups, ref="UK", rel_band=(0.90, 1.10), di_band=(0.80, 1.25), min_n=100, n_boot=300, seed=0, cluster=None) -> dict:
    """Return the group table and acceptance checks. CIs for the ratios/differences come from a bootstrap (clustered by customer if given)."""
    y = np.asarray(y); pred = np.asarray(pred); groups = np.asarray(groups)
    t = group_table(y, pred, groups, min_n); ov = overall(y, pred)
    others = [g for g in t.index if g != ref]
    out = {"table": t, "overall": ov, "ref": ref, "comparisons": {}}
    rng = np.random.default_rng(seed)
    cl = np.asarray(cluster) if cluster is not None else np.arange(len(y)); uc = pd.unique(cl); idx_by = pd.Series(np.arange(len(y))).groupby(cl).apply(np.array)
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(uc, size=len(uc), replace=True); ii = np.concatenate([idx_by[c] for c in pick])
        tb = group_table(y[ii], pred[ii], groups[ii], min_n); boots.append(tb)
    for g in others:
        a, b = t.loc[g], t.loc[ref]
        def ratio(x, z): return x / z if z and not np.isnan(z) and z > 0 else np.nan
        comp = {"n": int(a.n), "sufficient_n": bool(a.sufficient_n),
                "demographic_parity_difference": a.selection_rate - b.selection_rate, "disparate_impact_ratio": ratio(a.selection_rate, b.selection_rate),
                "tpr_difference": a.tpr - b.tpr, "fpr_difference": a.fpr - b.fpr,
                "equalized_odds_difference": max(abs(a.tpr - b.tpr), abs(a.fpr - b.fpr)),
                "tpr_vs_overall": ratio(a.tpr, ov["tpr"]), "fpr_vs_overall": ratio(a.fpr, ov["fpr"]), "selection_vs_overall": ratio(a.selection_rate, ov["selection_rate"])}
        def ci(f):
            v = [f(tb) for tb in boots if g in tb.index and ref in tb.index]; v = [x for x in v if x == x]
            return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if v else (np.nan, np.nan)
        comp["ci_demographic_parity_difference"] = ci(lambda tb: tb.loc[g, "selection_rate"] - tb.loc[ref, "selection_rate"])
        comp["ci_disparate_impact_ratio"] = ci(lambda tb: tb.loc[g, "selection_rate"] / tb.loc[ref, "selection_rate"])
        comp["ci_tpr_difference"] = ci(lambda tb: tb.loc[g, "tpr"] - tb.loc[ref, "tpr"])
        comp["ci_fpr_difference"] = ci(lambda tb: tb.loc[g, "fpr"] - tb.loc[ref, "fpr"])
        di_ok = di_band[0] <= comp["disparate_impact_ratio"] <= di_band[1]
        tpr_ok = rel_band[0] <= comp["tpr_vs_overall"] <= rel_band[1]; fpr_ok = rel_band[0] <= comp["fpr_vs_overall"] <= rel_band[1]
        comp["checks"] = {"disparate_impact_in_0.8_1.25": bool(di_ok), "tpr_within_10pct_of_overall": bool(tpr_ok), "fpr_within_10pct_of_overall": bool(fpr_ok)}
        comp["all_checks_pass"] = bool(di_ok and tpr_ok and fpr_ok)
        out["comparisons"][g] = comp
    return out
