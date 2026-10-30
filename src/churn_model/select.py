"""Model selection on VALIDATION dates only, applying the pre-declared rule and the fairness gate, then writes reports/model/selection.json.
Rule: rank candidates by validation ROC-AUC; any candidate within 0.005 AUC of the best is ordered by interpretability (logreg < lightgbm < random forest).
Gate: UK vs Non-UK validation check: disparate impact ratio in [0.80, 1.25] and TPR/FPR within +/-10% of overall. First ranked candidate that passes is selected.
Run: PYTHONPATH=src python -m churn_model.select"""
import json
import joblib, pandas as pd
from . import dataset as D, fairness as F, tracking
from .train import INTERPRETABILITY_RANK

def main():
    c = tracking.cfg(); R = tracking.ROOT / "reports" / "model"
    s1 = json.loads((R / "stage1_validation_results.json").read_text())
    df = pd.read_parquet(tracking.ROOT / "data" / "modeling" / "churn_snapshots.parquet"); va = df[D.split_masks(df, c)["validation"]]
    cand = {k: v for k, v in s1["results"].items() if v["kind"] == "candidate"}
    top = max(v["val"]["roc_auc"] for v in cand.values())
    order = sorted(cand, key=lambda k: (0, INTERPRETABILITY_RANK[k]) if top - cand[k]["val"]["roc_auc"] <= 0.005 else (1, -cand[k]["val"]["roc_auc"]))
    gate = {}
    for k in order:
        est = joblib.load(tracking.ROOT / "models" / "candidates" / f"{k}.joblib"); p = est.predict_proba(va[D.FEATURES])[:, 1]
        a = F.assess(va.churn, (p >= cand[k]["threshold"]).astype(int), va.group_uk, cluster=va.customer_key, n_boot=100)
        g = a["comparisons"]["Non-UK"]; gate[k] = {"passes": g["all_checks_pass"], "checks": g["checks"], "disparate_impact_ratio": g["disparate_impact_ratio"],
                                                  "tpr_vs_overall": g["tpr_vs_overall"], "fpr_vs_overall": g["fpr_vs_overall"]}
    final = next((k for k in order if gate[k]["passes"]), None)
    sel = {"final_model": final, "ranking_after_rule": order, "selection_rule": __doc__.strip().split("\n")[0:3], "validation_roc_auc": {k: v["val"]["roc_auc"] for k, v in cand.items()},
           "validation_cv_auc": {k: [v["cv_mean_auc"], v["cv_std_auc"]] for k, v in cand.items()}, "fairness_gate_validation": gate,
           "mitigation_triggered_on_validation": final is None or not gate[final]["passes"], "written_before_test_evaluation": True,
           "dataset_hash": s1["dataset_hash"], "code_hash_at_selection": s1["code_hash"], "iteration": tracking.ITERATION}
    (R / "selection.json").write_text(json.dumps(sel, indent=2, default=float)); print(json.dumps({k: sel[k] for k in ("final_model", "ranking_after_rule", "validation_roc_auc", "mitigation_triggered_on_validation")}, indent=1)); print(json.dumps(gate, indent=1, default=float))

if __name__ == "__main__":
    main()
