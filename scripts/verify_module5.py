"""Cross-checks the Module 5 deck and dashboard evidence against the recorded Module 4 results. Exits non-zero on any mismatch.
Run: PYTHONPATH=src python scripts/verify_module5.py [--deck deck/Module5_Churn_Insights.pptx]"""
import json, re, sys
from pathlib import Path
from pptx import Presentation
ROOT = Path(__file__).resolve().parents[1]; bad = []
def chk(label, ok):
    print(("PASS " if ok else "FAIL ") + label); 
    if not ok: bad.append(label)
deck = Path(sys.argv[sys.argv.index("--deck") + 1]) if "--deck" in sys.argv else ROOT / "deck/Module5_Churn_Insights.pptx"
E = json.loads((ROOT / "dashboard/data/dashboard_evidence.json").read_text()); fin = json.loads((ROOT / "reports/model/final_test_results.json").read_text())
mit = json.loads((ROOT / "reports/model/mitigation_results.json").read_text()); W = json.loads((ROOT / "deck/whatif_data.json").read_text())
prs = Presentation(str(deck)); slides = list(prs.slides)
texts = [" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) + " " + " ".join(c.text for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells) for s in slides]
notes = [s.notes_slide.notes_text_frame.text if s.has_notes_slide else "" for s in slides]; allt = " ".join(texts + notes)
titles = [next((sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.name == "Title"), "") for s in slides]
chk("15 slides in total (12 main + 3 appendix)", len(slides) == 15 and titles[12].startswith("Appendix A") and titles[14].startswith("Appendix C") and not titles[11].startswith("Appendix"))
chk("no recommendation or executive-summary slide", not any(re.search(r"(?i)\brecommendation|executive summary", t) for t in titles))
chk("every slide has speaker notes of at least 300 characters", all(len(x) >= 300 for x in notes))
L = E["headline"]["logreg"]; B = E["headline"]["baseline_recency_rule"]; ci = E["headline"]["logreg_ci"]
for label, v in [("ROC-AUC", f"{L['roc_auc']:.3f}"), ("baseline AUC", f"{B['roc_auc']:.3f}"), ("recall", f"{100*L['recall']:.1f}%"), ("precision", f"{100*L['precision']:.1f}%"), ("flag rate", f"{100*L['flag_rate']:.1f}%"), ("AUC CI low", f"{ci['roc_auc'][0]:.3f}"), ("AUC CI high", f"{ci['roc_auc'][1]:.3f}"), ("threshold", f"{E['meta']['threshold']:.3f}"), ("false alarms", f"{L['fp']:,}"), ("misses", f"{L['fn']:,}")]:
    chk(f"deck states {label} = {v}", v in allt)
c = E["fairness"]["comparisons"]["Non-UK"]; fpr = {k: v for k, v in E["fairness"]["mitigation"].items()}
for label, v in [("DI", f"{c['disparate_impact_ratio']:.3f}"), ("FPR diff", f"{c['fpr_difference']:.3f}"), ("FPR diff CI", f"{c['ci_fpr_difference'][0]:.3f}"), ("TPR diff", f"{c['tpr_difference']:.3f}")]: chk(f"deck states fairness {label} = {v}", v in allt)
gap = lambda k: fpr[k]["test_exploratory"]["fpr_NonUK"] - fpr[k]["test_exploratory"]["fpr_UK"]
chk("mitigation figures in appendix match mitigation_results.json (-0.024 gap; recall 0.953 -> 0.880; EO diff 0.024 -> 0.047)", f"{fpr['M0_unmitigated_selected_model']['test_exploratory']['equalized_odds_difference']:.3f}" == "0.024" and f"{fpr['M1_threshold_optimizer_equalized_odds']['test_exploratory']['equalized_odds_difference']:.3f}" == "0.047" and "0.047" in allt and "0.024" in allt)
chk("group-threshold recall 0.880 matches mitigation_results.json", f"{fpr['M1_threshold_optimizer_equalized_odds']['test_exploratory']['recall']:.3f}" == "0.880" and "0.880" in allt)
chk("test prevalence 0.60 matches meta", round(E["meta"]["prevalence"], 2) == 0.60)
chk("unseen-customer AUC 0.772 matches recorded subset", f"{E['subsets']['customers_unseen_in_training']['roc_auc']:.3f}" == "0.772" and "0.772" in allt)
a = E["cases"]["A_typical_true_positive"]["profile"]; d = E["cases"]["D_missed_churner_false_negative"]["profile"]; cc = E["cases"]["C_confident_false_positive"]["profile"]
chk("case narratives match profiles (A: 2 invoices/372 days tenure/330 days silent; C: 1 invoice 512 days earlier; D: 31 invoices, 28 days)", a["n_inv_all"] == 2 and a["tenure_days"] == 372 and a["recency_days"] == 330 and cc["n_inv_all"] == 1 and cc["recency_days"] == 512 and d["n_inv_all"] == 31 and d["recency_days"] == 28)
A = W["cases"]["A_typical_true_positive"]["scores_by_extra_invoices"]; Cc = W["cases"]["C_confident_false_positive"]["scores_by_extra_invoices"]; thr = E["meta"]["threshold"]
chk("what-if: neither case A (0.382) nor case C (0.597) falls below the threshold within six extra invoices at a 90-day-old latest purchase", min(A) > thr and min(Cc) > thr)
chk("what-if data came from the same model version as the evidence", W["model_version"] == E["meta"]["model_version"] and abs(W["threshold"] - thr) < 1e-9)
chk("dashboard URL on slide 12 is a hyperlink", any(r.hyperlink.address for sh in slides[11].shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs if r.hyperlink and r.hyperlink.address))
chk("QR image present on slide 12", any(sh.shape_type == 13 for sh in slides[11].shapes))
chk("no customer identifiers in deck text", not re.search(r"(?i)customer_key|\b[0-9a-f]{32}\b", allt))
chk("deck makes no fairness or compliance certification claim", not re.search(r"(?i)(is|are|was) (legally |fully )?(compliant|certified)|has been certified|proves? (that )?the model is fair|is a fair model", allt))
print("\nRESULT:", "ALL CHECKS PASSED" if not bad else f"{len(bad)} FAILED: {bad}"); sys.exit(1 if bad else 0)
