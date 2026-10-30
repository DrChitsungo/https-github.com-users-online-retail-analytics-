"""Stage 1: baselines + candidate algorithms. Tuning uses purged time-forward CV inside the TRAIN dates only;
the validation dates choose the model and decision threshold; the test dates are not read here.
Run:  PYTHONPATH=src python -m churn_model.train"""
from __future__ import annotations
import json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import joblib, mlflow, numpy as np, pandas as pd
from scipy.stats import loguniform, randint, uniform
from sklearn.model_selection import RandomizedSearchCV
from . import dataset as D, tracking
from .common import (best_f1_threshold, df_hash, env_versions, fig_calibration, fig_confusion, fig_roc_pr, forward_chain_folds,
                     make_pipeline, metrics_at, stable_hash, RecencyRule)

ROOT = tracking.ROOT
OUT = ROOT / "models" / "candidates"; FIG = ROOT / "reports" / "model" / "figures"
SPACES = {
    "logreg": {"clf__C": loguniform(1e-3, 1e2), "clf__class_weight": [None, "balanced"]},
    "lightgbm": {"clf__n_estimators": randint(100, 600), "clf__learning_rate": loguniform(0.01, 0.2), "clf__num_leaves": randint(7, 64),
                 "clf__min_child_samples": randint(20, 200), "clf__subsample": uniform(0.6, 0.4), "clf__subsample_freq": [1],
                 "clf__colsample_bytree": uniform(0.5, 0.5), "clf__reg_lambda": loguniform(1e-2, 1e2)},
    "random_forest": {"clf__n_estimators": [200, 400], "clf__max_depth": [4, 6, 8, 12, 16, None], "clf__min_samples_leaf": randint(5, 60),
                      "clf__max_features": ["sqrt", 0.5]},
}
INTERPRETABILITY_RANK = {"logreg": 0, "lightgbm": 1, "random_forest": 2}


def code_hash() -> str:
    import hashlib
    h = hashlib.sha256()
    for p in sorted((ROOT / "src" / "churn_model").glob("*.py")) + [ROOT / "configs" / "churn.yaml"]:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "not-a-git-checkout"


def common_params(c, ds_hash, fact_sha, split_info):
    return {"dataset_hash": ds_hash, "fact_table_sha256": fact_sha[:16], "horizon_days": c["task"]["horizon_days"], "lookback_days": c["task"]["lookback_days"],
            "n_features": len(D.FEATURES), "seed": c["seeds"]["global"], "split_hash": stable_hash(c["split"]), "code_hash": code_hash(),
            "git_commit": git_commit(), **{f"split_{k}": v for k, v in split_info.items()}}


def log_eval_artifacts(tag, y, p, thr):
    FIG.mkdir(parents=True, exist_ok=True)
    paths = []
    for fn, args in ((fig_roc_pr, (y, p, tag, FIG / f"{tag}_roc_pr.png")), (fig_confusion, (y, p, thr, tag, FIG / f"{tag}_confusion.png")),
                     (fig_calibration, (y, p, tag, FIG / f"{tag}_calibration.png"))):
        fn(*args); paths.append(args[-1])
    for pth in paths:
        mlflow.log_artifact(str(pth), artifact_path="figures")


def main():
    c = tracking.cfg(); seed = c["seeds"]["global"]; tracking.setup(); OUT.mkdir(parents=True, exist_ok=True)
    df = D.build_all(c); masks = D.split_masks(df, c)
    ds_hash = df_hash(df.drop(columns=["snapshot"]).assign(snap=df.snapshot.astype("int64")))
    fact_sha = D.file_sha256(D.fact_path())
    (ROOT / "data" / "modeling").mkdir(parents=True, exist_ok=True); df.to_parquet(ROOT / "data" / "modeling" / "churn_snapshots.parquet")
    tr, va = df[masks["train"]], df[masks["validation"]]
    split_info = {"train_rows": len(tr), "train_customers": tr.customer_key.nunique(), "val_rows": len(va), "val_customers": va.customer_key.nunique(),
                  "test_rows_not_used_in_stage1": int(masks["test"].sum())}
    cp = common_params(c, ds_hash, fact_sha, split_info)
    folds = forward_chain_folds(df, masks["train"], c["cv"]["purge_months"])
    X_tr, y_tr, X_va, y_va = tr[D.FEATURES], tr.churn.values, va[D.FEATURES], va.churn.values
    # folds index positions in df; map to positions within tr
    pos = {i: k for k, i in enumerate(np.flatnonzero(masks["train"]))}
    cv = [([pos[i] for i in a], [pos[i] for i in b]) for a, b in folds]
    results = {}; stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def run(name, kind, fit_fn):
        with mlflow.start_run(run_name=f"{kind}-{name}-{stamp}") as r:
            mlflow.set_tags({"iteration": tracking.ITERATION, "stage": "validation", "model_kind": kind, "task": c["task"]["name"], "versions": json.dumps(env_versions())})
            mlflow.log_params(cp); t0 = time.time()
            est, extra = fit_fn()
            p_va = est.predict_proba(X_va)[:, 1] if hasattr(est, "predict_proba") else est.predict(X_va)
            thr = extra.pop("threshold", None)
            if thr is None:
                p_tr = est.predict_proba(X_tr)[:, 1]; thr = best_f1_threshold(y_tr if kind == "baseline" else y_va, p_va if kind != "baseline" else p_tr)
            m = metrics_at(y_va, p_va, thr)
            p_tr = est.predict_proba(X_tr)[:, 1]; m_tr = metrics_at(y_tr, p_tr, thr)
            mlflow.log_params({k: v for k, v in extra.items() if k != "cv_results"})
            mlflow.log_metrics({f"val_{k}": v for k, v in m.items() if isinstance(v, float) and not np.isnan(v)})
            mlflow.log_metrics({f"train_{k}": v for k, v in m_tr.items() if k in ("roc_auc", "pr_auc", "f1", "recall", "precision")})
            mlflow.log_metric("fit_seconds", time.time() - t0)
            log_eval_artifacts(f"{name}_val", y_va, p_va, thr)
            joblib.dump(est, OUT / f"{name}.joblib"); mlflow.log_artifact(str(OUT / f"{name}.joblib"), artifact_path="model")
            mlflow.log_dict(m, "validation_metrics.json")
            results[name] = {"kind": kind, "run_id": r.info.run_id, "val": m, "train": {k: m_tr[k] for k in ("roc_auc", "pr_auc", "f1", "recall", "precision")},
                             "threshold": thr, **{k: v for k, v in extra.items() if k != "cv_results"}}
            print(f"{name:28s} val AUC {m['roc_auc']:.4f} PR {m['pr_auc']:.4f} F1 {m['f1']:.4f} R {m['recall']:.3f} P {m['precision']:.3f} thr {thr:.3f}")

    # --- baselines (same protocol) ---
    def prevalence():
        e = make_pipeline("prevalence", seed).fit(X_tr, y_tr); return e, {"threshold": 0.0}   # majority-class: flag everyone if churn is the majority
    run("baseline_prevalence", "baseline", prevalence)

    def rule():
        e = RecencyRule().fit(X_tr, y_tr); return e, {"threshold": e.cut / 180.0, "recency_cutoff_days": e.cut}
    run("baseline_recency_rule", "baseline", rule)

    # --- candidates ---
    for name in ("logreg", "lightgbm", "random_forest"):
        def fit(name=name):
            s = RandomizedSearchCV(make_pipeline(name, seed), SPACES[name], n_iter=c["cv"]["n_iter"], scoring=c["cv"]["scoring"], cv=cv,
                                   random_state=seed, n_jobs=1, refit=True, error_score="raise")
            s.fit(X_tr, y_tr); i = s.best_index_
            ex = {"cv_mean_auc": float(s.cv_results_["mean_test_score"][i]), "cv_std_auc": float(s.cv_results_["std_test_score"][i]),
                  "cv_folds": len(cv), "search_n_iter": c["cv"]["n_iter"], "search_space": json.dumps({k: str(v) for k, v in SPACES[name].items()}),
                  **{f"best_{k}": v for k, v in s.best_params_.items()}}
            p = s.best_estimator_.predict_proba(X_va)[:, 1]; ex["threshold"] = best_f1_threshold(y_va, p)
            return s.best_estimator_, ex
        run(name, "candidate", fit)

    cand = {k: v for k, v in results.items() if v["kind"] == "candidate"}
    best = max(cand, key=lambda k: cand[k]["val"]["roc_auc"]); top = cand[best]["val"]["roc_auc"]
    near = [k for k in cand if top - cand[k]["val"]["roc_auc"] <= 0.005]
    selected = min(near, key=lambda k: INTERPRETABILITY_RANK[k])
    summary = {"stamp": stamp, "dataset_hash": ds_hash, "fact_table_sha256": fact_sha, "config_hash": stable_hash(c), "code_hash": code_hash(),
               "cv_folds": [{"train_snapshots": int(len(set(df.snapshot.iloc[a]))), "val_snapshot": str(df.snapshot.iloc[b[0]].date()), "n_train": len(a), "n_val": len(b)} for a, b in folds],
               "split_info": split_info, "results": results, "selection_rule": "highest validation ROC-AUC; if a more interpretable candidate is within 0.005 AUC, choose it. Fairness gate applied separately.",
               "best_by_auc": best, "selected_before_fairness_gate": selected}
    (ROOT / "reports" / "model").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "model" / "stage1_validation_results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("best by val AUC:", best, "| selected (rule):", selected)


if __name__ == "__main__":
    main()
