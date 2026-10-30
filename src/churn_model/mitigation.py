"""Fairness mitigation experiments (UK vs Non-UK operational grouping). Everything is FITTED on train/validation dates only.
M1 post-processing: fairlearn ThresholdOptimizer (equalized odds), fitted on validation predictions of the train-fitted model.
M2 pre-processing: Kamiran-Calders reweighing of train rows over (group, label) cells, logistic regression refit with the same hyper-parameters; threshold re-chosen on validation.
Before/after is reported on validation (same protocol) and on test. The test comparison is EXPLORATORY: the disparity was first observed on test,
so the final model selection (made before test) is not changed by it. Run: PYTHONPATH=src python -m churn_model.mitigation"""
import json
import joblib, mlflow, numpy as np, pandas as pd
from fairlearn.postprocessing import ThresholdOptimizer
from . import dataset as D, fairness as F, tracking
from .common import best_f1_threshold, env_versions, make_pipeline, metrics_at
from .train import code_hash, git_commit

def fair_summary(y, pred, groups, cluster):
    a = F.assess(y, pred, groups, cluster=cluster, n_boot=200, seed=5); g = a["comparisons"]["Non-UK"]
    return {"selection_rate_UK": float(a["table"].loc["UK", "selection_rate"]), "selection_rate_NonUK": float(a["table"].loc["Non-UK", "selection_rate"]), "tpr_UK": float(a["table"].loc["UK", "tpr"]), "tpr_NonUK": float(a["table"].loc["Non-UK", "tpr"]),
            "fpr_UK": float(a["table"].loc["UK", "fpr"]), "fpr_NonUK": float(a["table"].loc["Non-UK", "fpr"]), "demographic_parity_difference": g["demographic_parity_difference"], "disparate_impact_ratio": g["disparate_impact_ratio"],
            "equalized_odds_difference": g["equalized_odds_difference"], "tpr_vs_overall": g["tpr_vs_overall"], "fpr_vs_overall": g["fpr_vs_overall"], "ci_fpr_difference": list(g["ci_fpr_difference"]), "all_checks_pass": g["all_checks_pass"]}

def perf(y, pred):
    m = metrics_at(y, pred.astype(float), 0.5); return {k: m[k] for k in ("precision", "recall", "f1", "accuracy", "flag_rate")}

def main():
    c = tracking.cfg(); tracking.setup(); seed = c["seeds"]["global"]; R = tracking.ROOT / "reports" / "model"
    sel = json.loads((R / "selection.json").read_text()); s1 = json.loads((R / "stage1_validation_results.json").read_text())
    df = pd.read_parquet(tracking.ROOT / "data" / "modeling" / "churn_snapshots.parquet"); m = D.split_masks(df, c)
    tr, va, te = df[m["train"]], df[m["validation"]], df[m["test"]]
    base = joblib.load(tracking.ROOT / "models" / "candidates" / f"{sel['final_model']}.joblib"); thr = s1["results"][sel["final_model"]]["threshold"]
    params = {k[len("best_clf__"):]: v for k, v in s1["results"][sel["final_model"]].items() if k.startswith("best_clf__")}
    if params.get("class_weight") in ("None", None): params["class_weight"] = None
    out = {}
    def add(name, vpred, tpred, extra=None):
        out[name] = {"validation": {**perf(va.churn.values, vpred), **fair_summary(va.churn.values, vpred, va.group_uk.values, va.customer_key.values)},
                     "test_exploratory": {**perf(te.churn.values, tpred), **fair_summary(te.churn.values, tpred, te.group_uk.values, te.customer_key.values)}, **(extra or {})}
    vp = (base.predict_proba(va[D.FEATURES])[:, 1] >= thr).astype(int); tp = (base.predict_proba(te[D.FEATURES])[:, 1] >= thr).astype(int)
    add("M0_unmitigated_selected_model", vp, tp)
    # M1
    to = ThresholdOptimizer(estimator=base, constraints="equalized_odds", objective="balanced_accuracy_score", prefit=True, predict_method="predict_proba")
    to.fit(va[D.FEATURES], va.churn, sensitive_features=va.group_uk)
    v1 = to.predict(va[D.FEATURES], sensitive_features=va.group_uk, random_state=seed); t1 = to.predict(te[D.FEATURES], sensitive_features=te.group_uk, random_state=seed)
    add("M1_threshold_optimizer_equalized_odds", np.asarray(v1), np.asarray(t1), {"note": "fitted on validation; validation numbers are in-sample for the optimizer"})
    # M2
    w = tr.assign(cell=tr.group_uk + "_" + tr.churn.astype(str)); pg = tr.group_uk.value_counts(normalize=True); py = tr.churn.value_counts(normalize=True); pc = w.cell.value_counts(normalize=True)
    sw = np.array([pg[g] * py[y_] / pc[f"{g}_{y_}"] for g, y_ in zip(tr.group_uk, tr.churn)])
    est = make_pipeline("logreg", seed, **params); est.fit(tr[D.FEATURES], tr.churn, clf__sample_weight=sw)
    pv = est.predict_proba(va[D.FEATURES])[:, 1]; thr2 = best_f1_threshold(va.churn, pv)
    add("M2_reweighing_refit", (pv >= thr2).astype(int), (est.predict_proba(te[D.FEATURES])[:, 1] >= thr2).astype(int), {"threshold": thr2, "val_roc_auc": metrics_at(va.churn, pv, thr2)["roc_auc"],
        "test_roc_auc": metrics_at(te.churn, est.predict_proba(te[D.FEATURES])[:, 1], thr2)["roc_auc"]})
    for name, r in out.items():
        with mlflow.start_run(run_name=f"mitigation-{name}"):
            mlflow.set_tags({"iteration": tracking.ITERATION, "stage": "mitigation", "model_kind": "mitigation", "note": "fitted on train/validation only; test numbers exploratory (disparity first seen on test)", "versions": json.dumps(env_versions())})
            mlflow.log_params({"method": name, "dataset_hash": s1["dataset_hash"], "code_hash": code_hash(), "git_commit": git_commit(), "grouping": "UK vs Non-UK"})
            for split in ("validation", "test_exploratory"):
                mlflow.log_metrics({f"{split}_{k}": v for k, v in r[split].items() if isinstance(v, float) and not np.isnan(v)})
    (R / "mitigation_results.json").write_text(json.dumps(out, indent=2, default=float))
    for name, r in out.items():
        for split in ("validation", "test_exploratory"):
            x = r[split]; print(f"{name:42s} {split:16s} P {x['precision']:.3f} R {x['recall']:.3f} F1 {x['f1']:.3f} flag {x['flag_rate']:.3f} | DI {x['disparate_impact_ratio']:.3f} TPR/ov {x['tpr_vs_overall']:.3f} FPR/ov {x['fpr_vs_overall']:.3f} EOdiff {x['equalized_odds_difference']:.3f} pass {x['all_checks_pass']}")

if __name__ == "__main__":
    main()
