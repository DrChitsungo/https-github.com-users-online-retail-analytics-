"""Customer-segment audit (behavioural, NOT demographic and NOT protected) for the Module 4 churn model.

Reads the recorded Module 4 test predictions (nothing is retrained, no threshold changes) and reports flag rate, lapsers caught (TPR) and
false-alarm rate (FPR) with 95% intervals for three behavioural tertile segmentations: tenure, spend and purchase frequency.
Tertile cut-offs come from the TRAINING snapshots only, so they are fixed before the test period is looked at.
The middle tier is the reference. Run: PYTHONPATH=src python scripts/segment_audit.py
Writes reports/model/segment_audit.json. This is an exploratory descriptive audit; it does not change the model or the decision rule.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
from churn_model import dataset as D, tracking, fairness as F

ROOT = Path(__file__).resolve().parents[1]
cfg = tracking.cfg(); meta = json.loads((ROOT / "models/churn_logreg_v1.0.0.metadata.json").read_text())
df = pd.read_parquet(ROOT / "data/modeling/churn_snapshots.parquet"); masks = D.split_masks(df, cfg)
tr, te = df[masks["train"]], df[masks["test"]].reset_index(drop=True)
tp = pd.read_parquet(ROOT / "data/modeling/test_predictions.parquet").reset_index(drop=True)
assert len(te) == len(tp) and (te.customer_key.values == tp.customer_key.values).all() and (pd.to_datetime(te.snapshot).values == pd.to_datetime(tp.snapshot).values).all(), "row alignment"
assert abs(tp.pred.mean() - 0.676) < 0.002

DIMS = {"tenure_tier": ("tenure_days", "Days since first purchase"), "spend_tier": ("rev_all", "Revenue, all history"), "frequency_tier": ("n_inv_all", "Invoices, all history")}
out = {"label": "customer-segment audit: BEHAVIOURAL segments, not demographic and not protected characteristics", "model_version": meta["model_version"], "threshold": meta["threshold"],
       "status": "exploratory descriptive audit on the recorded test predictions; no retraining, no threshold change", "cutoffs_from": "training snapshots only (33.3rd and 66.7th percentiles)",
       "reference_tier": "Mid", "dimensions": {}}
for name, (col, desc) in DIMS.items():
    q1, q2 = np.percentile(tr[col].dropna(), [100 / 3, 200 / 3])
    seg = np.where(te[col] <= q1, "Low", np.where(te[col] <= q2, "Mid", "High"))
    a = F.assess(tp.churn.values, tp.pred.values, seg, ref="Mid", cluster=tp.customer_key.values, n_boot=300, seed=0)
    t = a["table"].reindex(["Low", "Mid", "High"])
    rows = {}
    for g in t.index:
        r = t.loc[g]; c = a["comparisons"].get(g, {})
        rows[g] = {"n": int(r.n), "prevalence": float(r.prevalence), "flag_rate": float(r.selection_rate), "flag_rate_ci": [float(r.sel_lo), float(r.sel_hi)],
                   "tpr": None if r.tpr != r.tpr else float(r.tpr), "tpr_ci": [None if r.tpr_lo != r.tpr_lo else float(r.tpr_lo), None if r.tpr_hi != r.tpr_hi else float(r.tpr_hi)],
                   "fpr": None if r.fpr != r.fpr else float(r.fpr), "fpr_ci": [None if r.fpr_lo != r.fpr_lo else float(r.fpr_lo), None if r.fpr_hi != r.fpr_hi else float(r.fpr_hi)],
                   "precision": None if r.precision != r.precision else float(r.precision), "sufficient_n": bool(r.sufficient_n),
                   **({"vs_mid": {k: (None if (isinstance(v, float) and v != v) else v) for k, v in c.items() if k in ("tpr_difference", "fpr_difference", "ci_tpr_difference", "ci_fpr_difference", "ci_demographic_parity_difference", "demographic_parity_difference")}} if c else {})}
    out["dimensions"][name] = {"variable": col, "description": desc, "cutoffs": [float(q1), float(q2)], "overall": {k: float(v) for k, v in a["overall"].items()}, "tiers": rows}
(ROOT / "reports/model/segment_audit.json").write_text(json.dumps(out, indent=1, default=float, allow_nan=False))
for name, d in out["dimensions"].items():
    print(f"\n{name} ({d['variable']}) cutoffs {d['cutoffs'][0]:.1f} / {d['cutoffs'][1]:.1f}")
    for g, r in d["tiers"].items():
        f = lambda x: "n/a" if x is None else f"{x:.3f}"
        print(f"  {g:>4} n={r['n']:>5} prev={r['prevalence']:.3f} flag={r['flag_rate']:.3f} TPR={f(r['tpr'])} [{f(r['tpr_ci'][0])},{f(r['tpr_ci'][1])}] FPR={f(r['fpr'])} [{f(r['fpr_ci'][0])},{f(r['fpr_ci'][1])}] suff={r['sufficient_n']}")
