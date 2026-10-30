"""Pipelines, purged time-forward CV, metrics and plots shared by training, evaluation, explainability and the API."""
from __future__ import annotations
import hashlib, json, platform
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score, roc_curve, precision_recall_curve)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
import lightgbm as lgb
from .dataset import FEATURES


def _imputer():
    return SimpleImputer(strategy="median")   # no missing-value indicators (iteration 2): single-invoice status is an explicit feature


def make_pipeline(name: str, seed: int, **params) -> Pipeline:
    """Every transform is inside the pipeline, so cross-validation and validation fit it on training rows only."""
    if name == "logreg":
        steps = [("impute", _imputer()), ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                 ("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=3000, random_state=seed, **params))]
    elif name == "lightgbm":
        steps = [("impute", _imputer()), ("clf", lgb.LGBMClassifier(random_state=seed, n_jobs=2, verbosity=-1, **params))]
    elif name == "random_forest":
        steps = [("impute", _imputer()), ("clf", RandomForestClassifier(random_state=seed, n_jobs=2, **params))]
    elif name == "prevalence":
        steps = [("clf", DummyClassifier(strategy="prior"))]
    else:
        raise ValueError(name)
    return Pipeline(steps)


def forward_chain_folds(df: pd.DataFrame, train_mask: pd.Series, purge_months: int = 3, min_train_snaps: int = 1):
    """Expanding-window folds over snapshot dates; training snapshots end >= purge_months before the fold's validation
    snapshot so the 90-day outcome windows of training rows finish before the validation prediction date."""
    snaps = sorted(df.loc[train_mask, "snapshot"].unique())
    folds = []
    for v in snaps:
        tr_snaps = [s for s in snaps if s <= pd.Timestamp(v) - pd.DateOffset(months=purge_months)]
        if len(tr_snaps) < min_train_snaps:
            continue
        tr = np.flatnonzero(train_mask & df.snapshot.isin(tr_snaps))
        va = np.flatnonzero(train_mask & (df.snapshot == v))
        folds.append((tr, va))
    return folds


def metrics_at(y, p, thr: float) -> dict:
    y = np.asarray(y); p = np.asarray(p); pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    out = {"n": int(len(y)), "prevalence": float(y.mean()), "threshold": float(thr), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
           "accuracy": float(accuracy_score(y, pred)),
           "precision": float(precision_score(y, pred, zero_division=0)) if (tp + fp) else float("nan"),
           "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)),
           "flag_rate": float(pred.mean())}
    if len(np.unique(y)) == 2:
        out.update(roc_auc=float(roc_auc_score(y, p)), pr_auc=float(average_precision_score(y, p)), brier=float(brier_score_loss(y, np.clip(p, 0, 1))))
    else:
        out.update(roc_auc=float("nan"), pr_auc=float("nan"), brier=float("nan"))
    return out


def best_f1_threshold(y, p) -> float:
    grid = np.unique(np.round(np.quantile(p, np.linspace(0.02, 0.98, 97)), 6))
    best, bt = -1, 0.5
    for t in grid:
        f = f1_score(y, (p >= t).astype(int), zero_division=0)
        if f > best:
            best, bt = f, float(t)
    return bt


def fig_roc_pr(y, p, title, path):
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
    fpr, tpr, _ = roc_curve(y, p); ax[0].plot(fpr, tpr, color="#1C7C7D"); ax[0].plot([0, 1], [0, 1], "--", color="#999")
    ax[0].set(xlabel="False positive rate", ylabel="True positive rate", title=f"ROC (AUC {roc_auc_score(y, p):.3f})")
    pr, rc, _ = precision_recall_curve(y, p); ax[1].plot(rc, pr, color="#D95D39"); ax[1].axhline(np.mean(y), ls="--", color="#999")
    ax[1].set(xlabel="Recall", ylabel="Precision", title=f"Precision-recall (AP {average_precision_score(y, p):.3f})")
    fig.suptitle(title, fontsize=10); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_confusion(y, p, thr, title, path):
    cm = confusion_matrix(y, (np.asarray(p) >= thr).astype(int), labels=[0, 1])
    fig, ax = plt.subplots(figsize=(3.8, 3.4)); ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Pred retained", "Pred churn"], yticklabels=["Actual retained", "Actual churn"], title=title)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_calibration(y, p, title, path, bins=10):
    d = pd.DataFrame({"y": y, "p": p}); d["b"] = pd.qcut(d.p.rank(method="first"), bins, labels=False)
    g = d.groupby("b").agg(p=("p", "mean"), y=("y", "mean"))
    fig, ax = plt.subplots(figsize=(4, 3.6)); ax.plot(g.p, g.y, "o-", color="#1C7C7D"); ax.plot([0, 1], [0, 1], "--", color="#999")
    ax.set(xlabel="Mean predicted probability", ylabel="Observed churn rate", title=title); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def env_versions() -> dict:
    import sklearn, lightgbm, shap, mlflow, fairlearn
    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scikit-learn": sklearn.__version__,
            "lightgbm": lightgbm.__version__, "shap": shap.__version__, "mlflow": mlflow.__version__, "fairlearn": fairlearn.__version__}


def stable_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def df_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()[:16]


class RecencyRule:
    """Business baseline: flag as churn-risk if days since last purchase exceeds a cut-off chosen on TRAIN dates."""
    def __init__(self):
        self.cut = None

    def fit(self, X, y):
        cuts = np.arange(5, 181, 5)
        f = [metrics_at(y, X.recency_days.values, c_)["f1"] for c_ in cuts]
        self.cut = float(cuts[int(np.argmax(f))]); return self

    def predict_proba(self, X):
        s = np.clip(X.recency_days.values / 180.0, 0, 1); return np.c_[1 - s, s]
