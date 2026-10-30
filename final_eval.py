"""Stage 2: one-time evaluation on the untouched TEST dates. Model, hyper-parameters and threshold were fixed on validation dates
(see reports/model/selection.json, written before this script is run). Non-selected models are evaluated as report-only comparisons.
Run: PYTHONPATH=src python -m churn_model.final_eval"""
from __future__ import annotations
import json
from datetime import datetime, timezone
import joblib, mlflow, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from . import dataset as D, fairness as F, tracking
from .common import RecencyRule, env_versions, fig_calibration, fig_confusion, fig_roc_pr, metrics_at
from .train import FIG, code_hash, git_commit

ROOT = tracking.ROOT
def boot(y, p, thr, cl, n=300, seed=1):
    rng = np.random.default_rng(seed); cl = np.asarray(cl); uc = pd.unique(cl); idx = pd.Series(np.arange(len(y))).groupby(cl).apply(np.array)
    out = {k: [] for k in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy")}
    for _ in range(n):
        ii = np.concatenate([idx[c] for c in rng.choice(uc, len(uc), replace=True)]); m = metrics_at(y[ii], p[ii], thr)
        for k in out: out[k].append(m[k])
    return {k: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))) for k, v in out.items()}

def main():
    c = tracking.cfg(); tracking.setup()
    sel = json.loads((ROOT / "reports" / "model" / "selection.json").read_text()); name = sel["final_model"]
    s1 = json.loads((ROOT / "reports" / "model" / "stage1_validation_results.json").read_text())
    df = pd.read_parquet(ROOT / "data" / "modeling" / "churn_snapshots.parquet"); m = D.split_masks(df, c)
    te = df[m["test"]].reset_index(drop=True); seen = set(df[m["train"] | m["validation"]].customer_key)
    y = te.churn.values; res = {}; FIG.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for mn, r in s1["results"].items():
        est = joblib.load(ROOT / "models" / "candidates" / f"{mn}.joblib"); p = est.predict_proba(te[D.FEATURES])[:, 1]; thr = r["threshold"]
        met = metrics_at(y, p, thr); ci = boot(y, p, thr, te.customer_key.values) if mn in (name, "baseline_prevalence", "baseline_recency_rule") or True else {}
        res[mn] = {"test": met, "ci": ci, "kind": r["kind"], "val_roc_auc": r["val"]["roc_auc"], "threshold": thr}
        with mlflow.start_run(run_name=f"test-eval-{mn}-{stamp}"):
            mlflow.set_tags({"iteration": tracking.ITERATION, "stage": "test", "model_kind": r["kind"], "selected_final": str(mn == name), "versions": json.dumps(env_versions()),
                             "note": "single test evaluation; threshold and model fixed on validation" })
            mlflow.log_params({"model": mn, "dataset_hash": s1["dataset_hash"], "code_hash": code_hash(), "git_commit": git_commit(), "threshold": thr,
                               "test_rows": len(te), "test_customers": te.customer_key.nunique(), "parent_validation_run": r["run_id"]})
            mlflow.log_metrics({f"test_{k}": v for k, v in met.items() if isinstance(v, float) and not np.isnan(v)})
            if mn == name:
                for k, (lo, hi) in ci.items(): mlflow.log_metrics({f"test_{k}_ci_lo": lo, f"test_{k}_ci_hi": hi})
        if mn == name:
            p_sel = p; thr_sel = thr
            for fn, args in ((fig_roc_pr, (y, p, f"{name} - test", FIG / "final_test_roc_pr.png")), (fig_confusion, (y, p, thr, f"{name} - test", FIG / "final_test_confusion.png")),
                             (fig_calibration, (y, p, f"{name} - test calibration", FIG / "final_test_calibration.png"))): fn(*args)
    # subsets
    pred = (p_sel >= thr_sel).astype(int)
    te["p"] = p_sel; te["pred"] = pred; te["unseen"] = ~te.customer_key.isin(seen)
    sub = {}
    for label, mask in (("all_test", np.ones(len(te), bool)), ("customers_seen_in_training", ~te.unseen.values), ("customers_unseen_in_training", te.unseen.values),
                        *[(f"snapshot_{s.date()}", (te.snapshot == s).values) for s in sorted(te.snapshot.unique())]):
        sub[label] = metrics_at(y[mask], p_sel[mask], thr_sel)
    # operating points at fixed flag rates (descriptive; NOT used to choose the threshold)
    op = []
    for q in (0.2, 0.3, 0.4, 0.5, 0.6):
        t_ = float(np.quantile(p_sel, 1 - q)); mm = metrics_at(y, p_sel, t_); op.append({"flag_rate": q, "threshold": t_, "precision": mm["precision"], "recall": mm["recall"], "f1": mm["f1"], "lift": mm["precision"] / float(y.mean())})
    mean_p = float(p_sel.mean())
    # fairness on test
    fa = F.assess(y, pred, te.group_uk.values, cluster=te.customer_key.values, n_boot=500, seed=3)
    # per-country table (>=min n only reported with metrics; others marked insufficient)
    ct = F.group_table(y, pred, te.country.values, c["fairness"]["min_group_n"]).sort_values("n", ascending=False)
    # calibration by group (Brier)
    from sklearn.metrics import brier_score_loss
    brier = {g: float(brier_score_loss(y[(te.group_uk == g).values], p_sel[(te.group_uk == g).values])) for g in ("UK", "Non-UK")}
    # figure: fairness bars
    t = fa["table"]; fig, ax = plt.subplots(1, 3, figsize=(10, 3.4))
    for a, col, lo, hi, ttl in zip(ax, ("selection_rate", "tpr", "fpr"), ("sel_lo", "tpr_lo", "fpr_lo"), ("sel_hi", "tpr_hi", "fpr_hi"), ("Flag rate", "True-positive rate", "False-positive rate")):
        v = t[col].values; a.bar(t.index, v, color=["#1C7C7D", "#F2A541"], yerr=[v - t[lo].values, t[hi].values - v], capsize=4); a.set_title(ttl); a.set_ylim(0, 1)
        a.axhline(fa["overall"][col], ls="--", color="#555", lw=1)
    fig.suptitle("Test set: UK vs Non-UK (operational grouping), 95% Wilson intervals; dashed = overall", fontsize=9); fig.tight_layout(); fig.savefig(FIG / "final_test_fairness_groups.png", dpi=130); plt.close(fig)
    out = {"stamp": stamp, "final_model": name, "threshold": thr_sel, "test_rows": len(te), "test_customers": int(te.customer_key.nunique()), "test_prevalence": float(y.mean()),
           "models": res, "subsets": sub, "operating_points": op, "mean_predicted_probability": mean_p, "fairness": {"table": t.reset_index().to_dict("records"), "overall": fa["overall"], "comparisons": fa["comparisons"], "brier_by_group": brier,
                                                       "per_country": ct.reset_index().to_dict("records")}}
    (ROOT / "reports" / "model" / "final_test_results.json").write_text(json.dumps(out, indent=2, default=float))
    te[["customer_key", "snapshot", "group_uk", "country", "churn", "p", "pred"]].to_parquet(ROOT / "data" / "modeling" / "test_predictions.parquet")
    for mn, r in res.items():
        t_ = r["test"]; print(f"{mn:24s} AUC {t_['roc_auc']:.4f} PR {t_['pr_auc']:.4f} F1 {t_['f1']:.4f} P {t_['precision']:.3f} R {t_['recall']:.3f} Acc {t_['accuracy']:.3f} flag {t_['flag_rate']:.3f}")
    print("prevalence test", round(y.mean(), 3)); print({k: (round(v['roc_auc'], 4), v['n']) for k, v in sub.items()})
    print(t[["n", "prevalence", "selection_rate", "tpr", "fpr", "precision"]].round(3)); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in fa["comparisons"]["Non-UK"].items() if k in ("demographic_parity_difference", "disparate_impact_ratio", "tpr_difference", "fpr_difference", "tpr_vs_overall", "fpr_vs_overall", "checks", "ci_disparate_impact_ratio", "ci_tpr_difference", "ci_fpr_difference")})

if __name__ == "__main__":
    main()
