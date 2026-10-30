"""Proxy-effect check requested in Module 1 s2.3: does adding the country grouping (UK flag) as a PREDICTOR change performance or group gaps?
Same hyper-parameters as the selected logistic regression; validation dates only. Logged to MLflow as stage=validation-ablation.
Run: PYTHONPATH=src python -m churn_model.ablation"""
import json
import mlflow, numpy as np, pandas as pd
from . import dataset as D, tracking, fairness as F
from .common import best_f1_threshold, env_versions, make_pipeline, metrics_at
from .train import code_hash, git_commit

def main():
    c = tracking.cfg(); tracking.setup(); seed = c["seeds"]["global"]
    df = pd.read_parquet(tracking.ROOT / "data" / "modeling" / "churn_snapshots.parquet"); m = D.split_masks(df, c)
    s1 = json.loads((tracking.ROOT / "reports" / "model" / "stage1_validation_results.json").read_text())
    params = {k[len("best_clf__"):]: v for k, v in s1["results"]["logreg"].items() if k.startswith("best_clf__")}
    if params.get("class_weight") in ("None", None): params["class_weight"] = None
    out = {}
    for tag, extra in (("without_country_flag", []), ("with_country_flag", ["is_uk"])):
        d = df.assign(is_uk=(df.group_uk == "UK").astype(int)); cols = D.FEATURES + extra
        tr, va = d[m["train"]], d[m["validation"]]
        est = make_pipeline("logreg", seed, **params).fit(tr[cols], tr.churn)
        p = est.predict_proba(va[cols])[:, 1]; thr = best_f1_threshold(va.churn, p); met = metrics_at(va.churn, p, thr)
        a = F.assess(va.churn, (p >= thr).astype(int), va.group_uk, cluster=va.customer_key, n_boot=200)
        cmp = a["comparisons"]["Non-UK"]
        out[tag] = {"val": met, "dpd": cmp["demographic_parity_difference"], "di_ratio": cmp["disparate_impact_ratio"], "tpr_diff": cmp["tpr_difference"], "fpr_diff": cmp["fpr_difference"]}
        with mlflow.start_run(run_name=f"ablation-logreg-{tag}") as r:
            mlflow.set_tags({"iteration": tracking.ITERATION, "stage": "validation-ablation", "model_kind": "ablation", "versions": json.dumps(env_versions())})
            mlflow.log_params({"dataset_hash": s1["dataset_hash"], "code_hash": code_hash(), "git_commit": git_commit(), "predictors": ",".join(cols), "seed": seed,
                               **{f"hp_{k}": v for k, v in params.items()}})
            mlflow.log_metrics({f"val_{k}": v for k, v in met.items() if isinstance(v, float) and not np.isnan(v)})
            mlflow.log_metrics({"val_dp_difference": cmp["demographic_parity_difference"], "val_di_ratio": cmp["disparate_impact_ratio"], "val_tpr_diff": cmp["tpr_difference"], "val_fpr_diff": cmp["fpr_difference"]})
        print(tag, {k: round(v, 4) if isinstance(v, float) else v for k, v in {"auc": met["roc_auc"], "f1": met["f1"], **{k: out[tag][k] for k in ("dpd", "di_ratio", "tpr_diff", "fpr_diff")}}.items()})
    (tracking.ROOT / "reports" / "model" / "ablation_country_flag.json").write_text(json.dumps(out, indent=2, default=float))

if __name__ == "__main__":
    main()
