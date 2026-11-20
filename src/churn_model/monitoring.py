"""Batch monitoring for the churn model (capstone report Section 7): input drift, score drift, performance on matured outcomes and fairness.

Run:  PYTHONPATH=src python -m churn_model.monitoring          (needs the git-ignored data/modeling/churn_snapshots.parquet)

Historical simulation: the validation months are the reference; each later month is scored with the packaged champion model as if it
were a production month, and its 90-day outcomes (already matured in the data) are used for performance and fairness checks.
Drift uses Evidently (DataDriftPreset) plus a population stability index (PSI) computed here. Every output written by default is
aggregate (no customer keys, no rows); Evidently's own HTML reports are written to a git-ignored folder.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
import joblib, numpy as np, pandas as pd, yaml
from sklearn.metrics import recall_score, precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "churn_logreg_v1.0.0.joblib"
META = json.loads(MODEL.with_suffix(".metadata.json").read_text())
FEATURES, THRESHOLD = META["feature_order"], META["threshold"]


def psi(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    """Population stability index with quantile bins from the reference; missing values form their own bin."""
    ref, cur = pd.Series(ref, dtype=float), pd.Series(cur, dtype=float)
    edges = np.unique(np.nanquantile(ref.dropna(), np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:                      # (near-)constant input: compare the shares of each distinct value instead
        cats = sorted(set(ref.dropna()) | set(cur.dropna()))
        r = np.array([(ref == c).mean() for c in cats] + [ref.isna().mean()]); c_ = np.array([(cur == c).mean() for c in cats] + [cur.isna().mean()])
    else:
        edges[0], edges[-1] = -np.inf, np.inf
        def shares(s):
            h = np.histogram(s.dropna(), bins=edges)[0] / max(len(s), 1)
            return np.append(h, s.isna().mean())
        r, c_ = shares(ref), shares(cur)
    r, c_ = np.clip(r, 1e-4, None), np.clip(c_, 1e-4, None)
    return float(np.sum((c_ - r) * np.log(c_ / r)))


def evidently_drift(ref: pd.DataFrame, cur: pd.DataFrame, html_path: Path | None):
    from evidently import Report
    from evidently.presets import DataDriftPreset
    snap = Report([DataDriftPreset()]).run(current_data=cur, reference_data=ref)
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True); snap.save_html(str(html_path))
    res = snap.dict()["metrics"]
    share, per = None, {}
    for m in res:
        name, conf, val = m.get("metric_name", ""), m.get("config", {}), m.get("value")
        if name.startswith("DriftedColumnsCount"): share = float(val["share"])
        elif name.startswith("ValueDrift("):
            method = conf.get("method", ""); thr = conf.get("threshold")
            p_value = "p_value" in method.lower()          # p-value tests drift when value < threshold; distances when value >= threshold
            per[conf["column"]] = {"method": method, "value": round(float(val), 4), "threshold": thr,
                                   "drifted": bool(float(val) < thr) if p_value else bool(float(val) >= thr)}
    return share, per


def group_fairness(df: pd.DataFrame, t: dict):
    def rates(g):
        pos, neg = g[g.churn == 1], g[g.churn == 0]
        return {"n": len(g), "selection_rate": g.pred.mean(), "tpr": pos.pred.mean() if len(pos) else np.nan, "fpr": neg.pred.mean() if len(neg) else np.nan}
    allr, uk, non = rates(df), rates(df[df.group_uk == "UK"]), rates(df[df.group_uk == "Non-UK"])
    lo, hi = t["disparate_impact_band"]; rlo, rhi = t["relative_band"]
    di = non["selection_rate"] / uk["selection_rate"]
    out = {"uk_n": uk["n"], "non_uk_n": non["n"], "disparate_impact": di,
           "tpr_vs_overall": non["tpr"] / allr["tpr"], "fpr_vs_overall": non["fpr"] / allr["fpr"]}
    out["sufficient_n"] = non["n"] >= t["min_group_n"]
    out["breach"] = bool(out["sufficient_n"] and not (lo <= di <= hi and rlo <= out["tpr_vs_overall"] <= rhi and rlo <= out["fpr_vs_overall"] <= rhi))
    return out


def window_stats(df: pd.DataFrame):
    return {"n": len(df), "prevalence": df.churn.mean(), "mean_score": df.p.mean(), "flag_rate": df.pred.mean(),
            "recall": recall_score(df.churn, df.pred), "precision": precision_score(df.churn, df.pred), "roc_auc": roc_auc_score(df.churn, df.p)}


def run(cfg: dict, write_html: bool = True) -> dict:
    snaps = pd.read_parquet(ROOT / "data" / "modeling" / "churn_snapshots.parquet")
    snaps["snapshot"] = pd.to_datetime(snaps["snapshot"]).dt.strftime("%Y-%m-%d")
    pipe = joblib.load(MODEL)
    snaps["p"] = pipe.predict_proba(snaps[FEATURES])[:, 1]; snaps["pred"] = (snaps.p >= THRESHOLD).astype(int)
    t = cfg["thresholds"]
    ref = snaps[snaps.snapshot.isin(cfg["reference_snapshots"])]
    base = window_stats(ref)
    months = []
    for m in cfg["current_snapshots"]:
        cur = snaps[snaps.snapshot == m]
        html = (ROOT / cfg["outputs"]["evidently_html_dir"] / f"evidently_drift_{m[:7]}.html") if write_html else None
        share, per = evidently_drift(ref[FEATURES + ["p"]].rename(columns={"p": "score"}), cur[FEATURES + ["p"]].rename(columns={"p": "score"}), html)
        feat_psi = {f: psi(ref[f].to_numpy(), cur[f].to_numpy()) for f in FEATURES}
        score_psi = psi(ref.p.to_numpy(), cur.p.to_numpy())
        s, fair = window_stats(cur), group_fairness(cur, t)
        top = max(feat_psi, key=feat_psi.get)
        alerts = []
        if abs(s["mean_score"] - base["mean_score"]) > t["max_mean_score_shift"]: alerts.append("mean score shift")
        if abs(s["flag_rate"] - base["flag_rate"]) > t["max_flag_rate_shift"]: alerts.append("flag-rate shift")
        if max(feat_psi.values()) > t["psi_alert"]: alerts.append(f"input PSI > {t['psi_alert']} ({top})")
        if score_psi > t["psi_alert"]: alerts.append(f"score PSI > {t['psi_alert']}")
        if share is not None and share > t["max_drifted_feature_share"]: alerts.append("Evidently: most inputs drifted")
        if base["recall"] - s["recall"] > t["max_recall_drop"]: alerts.append("recall drop")
        if fair["breach"]: alerts.append("fairness band breached")
        months.append({"month": m[:7], "used_for": "test" if m in ("2011-08-01", "2011-09-01") else "unused (purge gap)",
                       **{k: round(float(v), 4) if isinstance(v, (float, np.floating)) else v for k, v in s.items()},
                       "score_psi": round(score_psi, 4), "max_input_psi": round(feat_psi[top], 4), "max_input_psi_feature": top,
                       "evidently_drifted_share": None if share is None else round(share, 4),
                       "evidently_drifted_features": sorted(k for k, v in per.items() if v["drifted"] and k != "score"),
                       "input_psi": {k: round(v, 4) for k, v in feat_psi.items()},
                       "fairness": {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in fair.items()},
                       "alerts": alerts, "status": "ALERT" if alerts else "OK"})
    import evidently
    return {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "model_version": META["model_version"], "threshold": THRESHOLD,
            "evidently_version": evidently.__version__, "kind": "historical batch simulation; not scheduled in production",
            "reference": {"snapshots": cfg["reference_snapshots"], **{k: round(float(v), 4) for k, v in base.items()}},
            "thresholds": t, "months": months,
            "privacy": "aggregate statistics only; no customer keys or rows"}


def plot(summary: dict, path: Path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    ms = [m["month"] for m in summary["months"]]; ref = summary["reference"]; t = summary["thresholds"]
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    ax[0].plot(ms, [m["max_input_psi"] for m in summary["months"]], "o-", color="#1C7C7D",
               label="largest input PSI (" + ", ".join(sorted({m["max_input_psi_feature"] for m in summary["months"]})) + ")")
    ax[0].plot(ms, [m["score_psi"] for m in summary["months"]], "s-", color="#F2A541", label="score PSI")
    ax[0].axhline(t["psi_alert"], ls="--", color="#B23A48", lw=1, label=f"alert {t['psi_alert']}"); ax[0].set_title("Drift against validation months"); ax[0].legend(fontsize=8)
    ax[1].plot(ms, [m["flag_rate"] for m in summary["months"]], "o-", color="#1C7C7D", label="flag rate")
    ax[1].plot(ms, [m["recall"] for m in summary["months"]], "s-", color="#33415C", label="recall")
    ax[1].plot(ms, [m["precision"] for m in summary["months"]], "^-", color="#F2A541", label="precision")
    ax[1].axhline(ref["recall"] - t["max_recall_drop"], ls="--", color="#B23A48", lw=1, label="recall floor")
    ax[1].set_ylim(0.5, 1.0); ax[1].set_title("Operating point on matured outcomes"); ax[1].legend(fontsize=8)
    lo, hi = t["relative_band"]
    ax[2].plot(ms, [m["fairness"]["tpr_vs_overall"] for m in summary["months"]], "o-", color="#1C7C7D", label="non-UK TPR / overall")
    ax[2].plot(ms, [m["fairness"]["fpr_vs_overall"] for m in summary["months"]], "s-", color="#F2A541", label="non-UK FPR / overall")
    ax[2].plot(ms, [m["fairness"]["disparate_impact"] for m in summary["months"]], "^-", color="#33415C", label="disparate impact")
    ax[2].axhspan(lo, hi, color="#1C7C7D", alpha=0.08, label="±10% band"); ax[2].set_ylim(0.7, 1.3); ax[2].set_title("UK vs non-UK (operational grouping)"); ax[2].legend(fontsize=8)
    for a in ax: a.tick_params(labelsize=8); a.grid(alpha=0.2)
    fig.suptitle(f"Churn model v{summary['model_version']}: monthly batch monitoring (historical simulation)", fontsize=11); fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=150); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/monitoring.yaml"); ap.add_argument("--no-html", action="store_true")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load((ROOT / a.config).read_text())
    s = run(cfg, write_html=not a.no_html)
    o = cfg["outputs"]
    for p in (o["summary"], o["dashboard_copy"]):
        (ROOT / p).parent.mkdir(parents=True, exist_ok=True); (ROOT / p).write_text(json.dumps(s, indent=2) + "\n")
    plot(s, ROOT / o["chart"])
    for m in s["months"]:
        print(f"{m['month']}  {m['status']:5}  flag {m['flag_rate']:.3f}  recall {m['recall']:.3f}  AUC {m['roc_auc']:.3f}  maxPSI {m['max_input_psi']:.3f} ({m['max_input_psi_feature']})  "
              f"Evidently drifted {m['evidently_drifted_share']}  alerts: {', '.join(m['alerts']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
