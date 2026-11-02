"""Descriptive check on the recorded Module 4 test predictions (nothing retrained, no threshold change).
The Marketing eligibility rule (at least 180 days of prior history) includes customers who have not bought for a long time, who are easy to rank as
churners. This reports the same metrics for the subset that also bought in the 180 days before the prediction date (the narrower population used before
1 November 2026), so readers can see how much of the headline comes from long-lapsed customers. Run: PYTHONPATH=src python scripts/active_subset_check.py
Writes reports/model/active_subset.json (aggregate only)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from churn_model import dataset as D, tracking

ROOT = Path(__file__).resolve().parents[1]; cfg = tracking.cfg()
df = pd.read_parquet(ROOT / "data/modeling/churn_snapshots.parquet"); te = df[D.split_masks(df, cfg)["test"]].reset_index(drop=True)
tp = pd.read_parquet(ROOT / "data/modeling/test_predictions.parquet").reset_index(drop=True)
assert len(te) == len(tp) and (te.customer_key.values == tp.customer_key.values).all()
rng = np.random.default_rng(0); keys = te.customer_key.values; uk = np.unique(keys)

def stats(mask):
    y, p, pr = tp.churn.values[mask], tp.p.values[mask], tp.pred.values[mask]
    tn, fp = int(((y == 0) & (pr == 0)).sum()), int(((y == 0) & (pr == 1)).sum()); tpn, fn = int(((y == 1) & (pr == 1)).sum()), int(((y == 1) & (pr == 0)).sum())
    return {"n": int(mask.sum()), "customers": int(len(np.unique(keys[mask]))), "prevalence": float(y.mean()), "roc_auc": float(roc_auc_score(y, p)), "precision": tpn / (tpn + fp), "recall": tpn / (tpn + fn),
            "fpr": fp / (fp + tn), "flag_rate": float(pr.mean()), "tp": tpn, "fp": fp, "fn": fn, "tn": tn}

def auc_ci(mask, n_boot=300):
    idx = {k: np.flatnonzero((keys == k) & mask) for k in uk}; idx = [v for v in idx.values() if len(v)]; out = []
    for _ in range(n_boot):
        pick = np.concatenate([idx[i] for i in rng.integers(0, len(idx), len(idx))]); y = tp.churn.values[pick]
        if 0 < y.sum() < len(y): out.append(roc_auc_score(y, tp.p.values[pick]))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]

res = {"label": "descriptive subset check on recorded test predictions; no retraining, no threshold change", "all_eligible": stats(np.ones(len(te), bool))}
act = (te.recency_days <= cfg["task"]["min_history_days"]).values; lap = ~act
for name, m in (("also_bought_in_prior_180_days", act), ("no_purchase_in_prior_180_days", lap)):
    res[name] = stats(m); res[name]["roc_auc_ci95_cluster_bootstrap"] = auc_ci(m)
res["all_eligible"]["roc_auc_ci95_cluster_bootstrap"] = auc_ci(np.ones(len(te), bool))
(ROOT / "reports/model/active_subset.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    if isinstance(v, dict): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items() if a != "roc_auc_ci95_cluster_bootstrap"}, v.get("roc_auc_ci95_cluster_bootstrap"))
