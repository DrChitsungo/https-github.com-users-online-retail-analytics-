// Builds the 15-slide Module 5 stakeholder deck (12 main + 3 appendix) from verified Module 4 evidence.
// Inputs: dashboard/data/dashboard_evidence.json, deck/whatif_data.json, deck/qr_dashboard.png.  Output: deck/Module5_Churn_Insights.pptx
// Usage: DASHBOARD_URL=<url> [DASHBOARD_VERIFIED=2026-11-01] node deck/build_module5_deck.js
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/root/.claude/skills/synced/afbd2cd8-330c-4bdc-ba57-b498a7c52ff0_bad5ed0e-07a5-4673-805c-226b568cdf11/pptx/scripts/apply_theme.js");

const E = JSON.parse(fs.readFileSync(path.join(__dirname, "../dashboard/data/dashboard_evidence.json"), "utf8"));
const W = JSON.parse(fs.readFileSync(path.join(__dirname, "whatif_data.json"), "utf8"));
const URL = process.env.DASHBOARD_URL || "https://huggingface.co/spaces/Bezzel/retail-churn-dashboard";
const VERIFIED = process.env.DASHBOARD_VERIFIED || "";
const REPO = "https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-";
const n = (x) => Number(x).toLocaleString("en-GB");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
const f3 = (x) => x.toFixed(3);
const M = E.meta, H = E.headline, L = H.logreg, B = H.baseline_recency_rule, CI = H.logreg_ci, F = E.fairness, C = F.comparisons["Non-UK"];
const T = Object.fromEntries(F.table.map((r) => [r.group, r]));

const THEME = {
  name: "RetailChurn", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B2A38", lt1: "FFFFFF", dk2: "12344D", lt2: "EEF3F5", accent1: "1C7C7D", accent2: "F2A541", accent3: "B23A48", accent4: "2E8B57", accent5: "6C7A89", accent6: "8FB8DE", hlink: "1C7C7D", folHlink: "6C7A89" },
};
const NAVY = "12344D", TEXT = "1B2A38", TEAL = "1C7C7D", AMBER = "F2A541", RED = "B23A48", SLATE = "6C7A89", LIGHT = "EEF3F5", WHITE = "FFFFFF", SKY = "8FB8DE", MUTED = "5B6B79", PALE = "DCEFEF";
const HF = "Cambria", BF = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: HF, bodyFontFace: BF };
pres.title = "What a 90-day churn model can and cannot tell Marketing";
pres.author = "Bezzel Chitsungo";
pres.subject = "BAN 6800 Module 5: Business Insights Presentation";
pres.defineSlideMaster({ title: "CONTENT", background: { color: WHITE }, slideNumber: { x: 9.1, y: 5.28, w: 0.5, h: 0.25, fontFace: BF, fontSize: 10, color: MUTED, align: "right" }, objects: [] });
pres.defineSlideMaster({ title: "DARK", background: { color: NAVY } });

function header(s, title) {
  s.addText(title, { x: 0.5, y: 0.2, w: 9, h: 0.8, fontFace: HF, fontSize: 22, bold: true, color: NAVY, margin: 0, valign: "middle", isTextBox: true, objectName: "Title" });
}
function footer(s, text) { s.addText(text, { x: 0.5, y: 5.28, w: 8.5, h: 0.25, fontFace: BF, fontSize: 10, color: MUTED, margin: 0, isTextBox: true, objectName: "Source" }); }
function card(s, x, y, w, h, fill = LIGHT, name = "Card") { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0.5 }, rectRadius: 0.08, objectName: name }); }
function stat(s, x, y, w, h, big, label, sub, color = TEAL) {
  card(s, x, y, w, h, LIGHT, "Stat card");
  s.addText(big, { x: x + 0.1, y: y + 0.05, w: w - 0.2, h: 0.62, fontFace: HF, fontSize: 30, bold: true, color, margin: 0, valign: "middle", isTextBox: true });
  s.addText(label, { x: x + 0.1, y: y + 0.68, w: w - 0.2, h: 0.5, fontFace: BF, fontSize: 12, bold: true, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  if (sub) s.addText(sub, { x: x + 0.1, y: y + 1.12, w: w - 0.2, h: h - 1.16, fontFace: BF, fontSize: 11, color: MUTED, margin: 0, valign: "top", isTextBox: true });
}
function tag(s, x, y, w, text, color) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.26, fill: { color }, line: { color }, rectRadius: 0.05, objectName: "Status tag" });
  s.addText(text, { x, y, w, h: 0.26, fontFace: BF, fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function bullets(s, items, x, y, w, h, fs = 13, color = TEXT, gap = 6) {
  s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: gap } })), { x, y, w, h, fontFace: BF, fontSize: fs, color, margin: 0, valign: "top", isTextBox: true });
}
function box(s, x, y, w, h, text, fill, color = WHITE, fs = 12) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 1 }, rectRadius: 0.08, objectName: "Diagram box" });
  s.addText(text, { x, y, w, h, fontFace: BF, fontSize: fs, bold: true, color, align: "center", valign: "middle", margin: 0.05, isTextBox: true });
}
function arrow(s, x1, y1, x2, y2, color = SLATE) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipH: x2 < x1, flipV: y2 < y1, line: { color, width: 1.5, endArrowType: "triangle" }, objectName: "Arrow" });
}
const chartBase = (title) => ({ showTitle: true, title, titleFontSize: 12, titleFontFace: BF, titleColor: TEXT, showLegend: false, catAxisLabelFontSize: 11, catAxisLabelFontFace: BF, catAxisLabelColor: TEXT,
  valAxisLabelFontFace: BF, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED, dataLabelFontSize: 11, dataLabelFontFace: BF, dataLabelColor: TEXT, valGridLine: { color: "D9E0E4", size: 0.5 }, catGridLine: { style: "none" } });
const ops = E.operating_points; const op20 = ops[0];

// ------------------------------------------------------------------------------------------------ 1 Title and objective
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("Which active customers may stop buying in the next 90 days?", { x: 0.6, y: 0.9, w: 5.7, h: 1.6, fontFace: HF, fontSize: 32, bold: true, color: WHITE, margin: 0, valign: "top", isTextBox: true, objectName: "Title" });
  s.addText("What the Module 4 churn model can and cannot tell Marketing, and how far to trust it", { x: 0.6, y: 2.6, w: 5.5, h: 0.8, fontFace: BF, fontSize: 16, color: SKY, margin: 0, isTextBox: true, objectName: "Subtitle" });
  s.addText("Bezzel Chitsungo", { x: 0.6, y: 3.65, w: 5.5, h: 0.4, fontFace: BF, fontSize: 20, bold: true, color: WHITE, margin: 0, isTextBox: true });
  s.addText("MSc Data Analytics, Nexford University  |  BAN 6800 Module 5", { x: 0.6, y: 4.05, w: 5.6, h: 0.32, fontFace: BF, fontSize: 14, color: SKY, margin: 0, isTextBox: true });
  s.addText("Audience: Marketing and CRM managers", { x: 0.6, y: 4.4, w: 5.5, h: 0.3, fontFace: BF, fontSize: 14, color: WHITE, margin: 0, isTextBox: true });
  card(s, 6.6, 1.0, 2.9, 3.4, "1B4A6B", "Objective card");
  s.addText("Communication objective", { x: 6.75, y: 1.1, w: 2.6, h: 0.35, fontFace: HF, fontSize: 15, bold: true, color: AMBER, margin: 0, isTextBox: true });
  s.addText([{ text: "Explain in plain language what the model predicts, how well it does, what drives it, who it treats differently, and what it cannot establish.", options: { breakLine: true, paraSpaceAfter: 8 } },
             { text: "Then let you explore it on a live dashboard.", options: {} }], { x: 6.75, y: 1.5, w: 2.6, h: 2.8, fontFace: BF, fontSize: 14, color: WHITE, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Title slide. This presentation continues the Retail Analytics Decision Support Platform from Modules 1 to 4 on the Online Retail II data (Chen, 2019). The task has not changed: the Module 4 model predicts whether a currently active customer will place no sales invoice in the 90 days after a prediction date. The audience is Marketing and CRM managers, the tactical stakeholders named in the Module 1 stakeholder table and in the Model Card as the users of the model. The goal is understanding and informed judgement, not a sales pitch for the model.");
}

// ------------------------------------------------------------------------------------------------ 2 Business problem
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Repeat customers drive revenue, so losing active ones quietly is costly");
  card(s, 0.5, 1.15, 4.3, 2.05, PALE, "Problem card");
  s.addText("The business problem (Module 1)", { x: 0.65, y: 1.22, w: 4.0, h: 0.32, fontFace: HF, fontSize: 14, bold: true, color: TEAL, margin: 0, isTextBox: true });
  bullets(s, ["A UK giftware and homeware retailer; repeat customers and wholesale accounts provide most revenue", "No integrated, analytics-driven way yet to turn transaction history into timely insight", "Module 1 retention target: +5 percentage points in repeat purchases within 12 months"], 0.65, 1.58, 4.0, 1.6, 12, TEXT, 4);
  s.addText("Who is involved", { x: 5.1, y: 1.15, w: 4.4, h: 0.32, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const st = [["Marketing and CRM managers", "Use the lists to plan retention campaigns", TEAL], ["Business leaders and Finance", "Care about spend and revenue effect", SLATE], ["Data and IT", "Run the pipeline and API", SLATE], ["AI Ethics Committee", "Owns the model-bias risk", SLATE]];
  st.forEach((r, i) => { const y = 1.5 + i * 0.42; s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.1, y, w: 0.1, h: 0.34, fill: { color: r[2] }, line: { color: r[2] }, rectRadius: 0.03 });
    s.addText([{ text: r[0] + ": ", options: { bold: true } }, { text: r[1] }], { x: 5.3, y, w: 4.2, h: 0.34, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "middle", isTextBox: true }); });
  s.addText("Who is affected by model-supported decisions", { x: 0.5, y: 3.4, w: 9, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const aff = [["Customers who are flagged", "May receive an offer or contact they did not need"], ["Customers who are missed", "Lose the chance of a timely offer"], ["Customers outside the UK", "Fewer in the data, so measured less precisely"]];
  aff.forEach((a, i) => { const x = 0.5 + i * 3.05; card(s, x, 3.75, 2.9, 1.35, LIGHT, "Affected card");
    s.addText(a[0], { x: x + 0.12, y: 3.82, w: 2.66, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: NAVY, margin: 0, valign: "top", isTextBox: true });
    s.addText(a[1], { x: x + 0.12, y: 4.25, w: 2.66, h: 0.8, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", isTextBox: true }); });
  footer(s, "Source: Module 1 Vision Document (stakeholder table, goals); Model Card section 2 (users)");
  s.addNotes("Why this matters: the Module 1 document says repeat customers and wholesale accounts provide most revenue and sets a retention goal of five percentage points more repeat purchases. Marketing is the primary audience because the Module 1 stakeholder table links Marketing to customer segments and campaign design, and the Model Card names Marketing and CRM analysts as the users. Ethical concerns carried from Module 1: unnecessary contact when a customer is flagged wrongly, missed customers, and possible differences in treatment by country. Likely question: is the 5-point target measured? No. It is a Module 1 goal; this model has no measured effect on it.");
}

// ------------------------------------------------------------------------------------------------ 3 Model purpose
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "The model scores each active customer on the chance they go quiet for 90 days");
  s.addText("Each prediction concerns one customer on one prediction date (T)", { x: 0.5, y: 1.1, w: 9, h: 0.3, fontFace: BF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  box(s, 0.5, 1.55, 3.3, 0.85, "Look back 180 days\nCustomer must have bought at least once", SLATE, WHITE, 12);
  box(s, 4.1, 1.55, 1.7, 0.85, "Prediction date T", NAVY, WHITE, 13);
  box(s, 6.1, 1.55, 3.4, 0.85, "Next 90 days: any sales invoice?\nNone = counted as churned", TEAL, WHITE, 12);
  arrow(s, 3.82, 1.97, 4.08, 1.97); arrow(s, 5.82, 1.97, 6.08, 1.97);
  const cols = [["Information used", "Only purchases made before T: recency, tenure, invoice counts, spend, product breadth, gaps between purchases, cancellations (18 features). No names, no country, no personal attributes."],
                ["What it outputs", `A risk score and a flag at ${f3(M.threshold)}. The score is a ranking aid, not a calibrated probability.`],
                ["Intended use", "Help a person decide whom to include in retention campaigns. Not for automated decisions about individuals."]];
  cols.forEach((c, i) => { const x = 0.5 + i * 3.05; card(s, x, 2.75, 2.9, 2.3, LIGHT, "Info card");
    s.addText(c[0], { x: x + 0.12, y: 2.82, w: 2.66, h: 0.32, fontFace: HF, fontSize: 14, bold: true, color: TEAL, margin: 0, isTextBox: true });
    s.addText(c[1], { x: x + 0.12, y: 3.2, w: 2.66, h: 1.8, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", isTextBox: true }); });
  tag(s, 6.1, 2.45, 3.4, "Windows (90 and 180 days) are PROPOSED, not agreed", AMBER);
  footer(s, "Source: Model Card sections 1-3; configs/churn.yaml; same task and model as Module 4 (v1.0.0, logistic regression)");
  s.addNotes("Plain language: pick a date, look at the customer's last 180 days of buying, and ask whether they will buy anything in the next 90 days. If not, the customer counts as churned. The model sees only purchase history before the date, which is checked by automated tests that change future invoices and confirm the features do not move. The score is a relative-risk ranking: the model was not recalibrated and the lapse rate moved from 57 percent in validation to 42 percent in test. The 90-day and 180-day windows are proposals; Module 2 left the window to be agreed with Marketing, and that agreement has not happened. Likely question: why not forecast demand or segment customers instead? Because Module 4 built the churn model; this deck stays with it.");
}

// ------------------------------------------------------------------------------------------------ 4 Key results
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "The model ranks customers better than a simple rule, but flags two in three");
  stat(s, 0.5, 1.15, 2.1, 2.0, f3(L.roc_auc), "Ranking quality (ROC-AUC)", `Rule of "longest-silent first": ${f3(B.roc_auc)}. Chance: 0.500. Interval ${f3(CI.roc_auc[0])}-${f3(CI.roc_auc[1])}.`);
  stat(s, 2.72, 1.15, 2.1, 2.0, pct(L.recall), "Lapsers caught (recall)", `Interval ${pct(CI.recall[0])}-${pct(CI.recall[1])}.`, TEAL);
  stat(s, 4.94, 1.15, 2.1, 2.0, pct(L.precision), "Flags that are right (precision)", `Flagging everyone would be right ${pct(L.prevalence)} of the time.`, AMBER);
  stat(s, 7.16, 1.15, 2.1, 2.0, pct(L.flag_rate), "Customers flagged", `At threshold ${f3(M.threshold)}.`, RED);
  s.addText("What this means in everyday terms", { x: 0.5, y: 3.35, w: 9, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, [`Of 100 customers who go on to lapse, about ${Math.round(L.recall * 100)} are on the flagged list.`,
              `Of 100 flagged customers, about ${Math.round(L.precision * 100)} lapse and ${100 - Math.round(L.precision * 100)} would have kept buying anyway.`,
              `Two in three active customers are flagged, so the default list is not very selective. Slide 5 shows shorter lists.`], 0.5, 3.7, 9, 1.4, 13, TEXT, 5);
  footer(s, `Source: held-out test, prediction dates Aug and Sep 2011; ${n(M.test_rows)} customer-snapshots, ${n(M.test_customers)} customers. 95% customer-clustered bootstrap intervals.`);
  s.addNotes(`Verified results on the held-out test period (not used to tune the model): ROC-AUC ${f3(L.roc_auc)} with a 95 percent interval of ${f3(CI.roc_auc[0])} to ${f3(CI.roc_auc[1])}; the recency-rule baseline scored ${f3(B.roc_auc)}. At the fixed threshold ${f3(M.threshold)}, recall is ${pct(L.recall)}, precision ${pct(L.precision)}, flag rate ${pct(L.flag_rate)}. LightGBM (${f3(H.lightgbm_auc)}) and random forest (${f3(H.random_forest_auc)}) were statistically indistinguishable, so the simpler logistic regression was chosen by a rule fixed before testing. Honest caveats: one test window; the test set was scored twice plus exploratory mitigation runs, disclosed in the Validation Report; the threshold was set to maximise F1 on validation data where the lapse rate was 57 percent, which is why it flags so many customers on test where the lapse rate was 42 percent. Likely question: is 0.765 good? It is a useful ranking improvement over a rule, not a precise predictor.`);
}

// ------------------------------------------------------------------------------------------------ 5 Visual summary
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Shorter lists are more accurate, but they miss more of the customers who lapse");
  const lab = ops.map((o) => pct(o.flag_rate, 0)).concat([pct(L.flag_rate, 0) + " (default)"]);
  const prec = ops.map((o) => o.precision).concat([L.precision]); const rec = ops.map((o) => o.recall).concat([L.recall]);
  s.addChart(pres.charts.LINE, [{ name: "Precision: flags that are right", labels: lab, values: prec }, { name: "Recall: lapsers caught", labels: lab, values: rec }],
    { x: 0.4, y: 1.1, w: 5.4, h: 3.9, ...chartBase("Precision and recall by list size"), showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: BF, chartColors: [TEAL, AMBER], lineSize: 3, lineDataSymbolSize: 8,
      valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0%", showValue: false, catAxisTitle: "Share of customers flagged", showCatAxisTitle: true, catAxisTitleFontSize: 11 });
  s.addChart(pres.charts.BAR, [{ name: "Customer-snapshots", labels: ["Flagged, lapsed", "Flagged, kept buying", "Not flagged, lapsed", "Not flagged, kept buying"], values: [L.tp, L.fp, L.fn, L.tn] }],
    { x: 5.9, y: 1.1, w: 3.7, h: 3.0, barDir: "bar", ...chartBase("Outcomes at the default threshold"), chartColors: [TEAL, AMBER, RED, SLATE], showValue: true, dataLabelFormatCode: "#,##0", catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40 });
  card(s, 5.9, 4.15, 3.7, 0.95, PALE, "Callout");
  s.addText(`Flag the top 20% and ${pct(op20.precision, 0)} of flags are right, but only ${pct(op20.recall, 0)} of lapsers are caught. The right list size is a business choice.`, { x: 6.0, y: 4.18, w: 3.5, h: 0.9, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  footer(s, "Source: final_test_results.json (operating points on the test period; illustrative, not tuned). Recall and precision defined on slide 4.");
  s.addNotes(`The left chart shows the trade-off the business controls by choosing how many customers to contact. Flagging the top 20 percent gives precision ${pct(op20.precision)} and recall ${pct(op20.recall)}; the default threshold flags ${pct(L.flag_rate)} and gives precision ${pct(L.precision)} and recall ${pct(L.recall)}. The right chart counts the two kinds of error at the default threshold: ${n(L.fp)} customers were flagged but kept buying, and ${n(L.fn)} lapsers were missed. Which error is costlier depends on what an offer costs and what a retained customer is worth; neither is measured in the project. Operating points were computed on the test set for illustration. Likely question: which list size should we use? This deck does not prescribe one; it shows the trade-off.`);
}

// ------------------------------------------------------------------------------------------------ 6 What drives predictions
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Purchase frequency and time as a customer drive scores most");
  const gi = Object.entries(E.global_shap.group_importance).sort((a, b) => b[1] - a[1]);
  s.addChart(pres.charts.BAR, [{ name: "Influence", labels: gi.map((g) => g[0]), values: gi.map((g) => +g[1].toFixed(2)) }],
    { x: 0.4, y: 1.1, w: 5.3, h: 3.95, barDir: "bar", ...chartBase("Average influence on the risk score, by behaviour group"), chartColors: [TEAL], showValue: true, dataLabelFormatCode: "0.00", catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 35 });
  s.addText("How to read it", { x: 6.0, y: 1.1, w: 3.5, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, ["More invoices over time goes with a lower score.", "Recent purchases (last 90 days) go with a lower score.", "At the same number of invoices, a longer-standing customer scores higher: fewer purchases per month.", "Gap statistics and cancellations matter least."], 6.0, 1.45, 3.5, 2.2, 12, TEXT, 4);
  card(s, 6.0, 3.75, 3.5, 1.3, "FBEFD9", "Caution card");
  s.addText("These are associations the model learned, not causes. Buying more invoices does not by itself make a customer stay. Related features share credit.", { x: 6.1, y: 3.8, w: 3.3, h: 1.2, fontFace: BF, fontSize: 12, bold: true, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  footer(s, `Source: SHAP (Lundberg & Lee, 2017), LinearExplainer, ${n(E.global_shap.explained_rows)} test rows; log-odds scale. LightGBM agrees on ${E.global_shap.agreement_with_lightgbm.top5_overlap} of its top 5 features.`);
  s.addNotes(`SHAP values measure how much each factor pushes one prediction up or down from the average; the chart averages the absolute push over ${n(E.global_shap.explained_rows)} randomly chosen test rows and sums features within each behaviour group so that related features are read together. Purchase frequency is the largest group (${gi[0][1].toFixed(2)}), then tenure (${E.global_shap.group_importance["Tenure"].toFixed(2)}), spend and product breadth. Direction comes from the sign of the relationship between each feature and its SHAP value. Important caveat: model explanations describe predictive association, not causation, and correlated features can offset one another (for example, recent revenue has a positive sign once invoice counts are accounted for). A LightGBM model agrees on only 3 of its top 5 features and the rank correlation is ${E.global_shap.agreement_with_lightgbm.spearman_rank_logreg_vs_lightgbm.toFixed(2)}, so individual feature rankings are somewhat model-dependent. Likely question: LIME? SHAP was used for global and local explanations; LIME was not run.`);
}

// ------------------------------------------------------------------------------------------------ 7 Individual explanations
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Three real customers show a correct flag, a false alarm and a missed lapser");
  const picks = [["A_typical_true_positive", "Typical correct flag", TEAL, "Only two invoices in 426 days and none in the last 90 raised the score."],
                 ["C_confident_false_positive", "False alarm", AMBER, "Bought twice four days apart, then 161 quiet days looked alarming, but they bought again."],
                 ["D_missed_churner_false_negative", "Missed lapser", RED, "A frequent, high-value customer (31 invoices) who last bought 28 days earlier. Nothing in the history warned of a lapse."]];
  const short = { "Invoices, last 90d": "No/few invoices, last 90 days", "Days since first purchase": "Long time as customer", "Revenue, last 90d": "Revenue, last 90 days", "Mean days between purchases": "Average gap between purchases",
                  "Recency / mean gap": "Silence vs usual gap", "Invoices (all history)": "Total invoices", "Revenue (all history)": "Total revenue", "Distinct products, 180d": "Product variety, 180 days" };
  picks.forEach((p, i) => {
    const c = E.cases[p[0]], x = 0.5 + i * 3.05; card(s, x, 1.1, 2.9, 3.95, LIGHT, "Case card");
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.1, w: 2.9, h: 0.08, fill: { color: p[2] }, line: { color: p[2] } });
    s.addText(p[1], { x: x + 0.12, y: 1.22, w: 2.66, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
    s.addText(`Score ${c.stored_score.toFixed(2)}, ${c.flagged ? "flagged" : "not flagged"}.\nActually ${c.actual_churn ? "lapsed" : "kept buying"}.`, { x: x + 0.12, y: 1.52, w: 2.66, h: 0.44, fontFace: BF, fontSize: 11, bold: true, color: p[2] === AMBER ? "8A5A00" : p[2], margin: 0, isTextBox: true });
    c.top_drivers.forEach((d, k) => { const y = 2.0 + k * 0.37, mx = 1.1, w = Math.max(0.05, Math.min(mx, Math.abs(d.shap_log_odds) / 2.4 * mx)), up = d.shap_log_odds > 0;
      s.addText(short[d.feature] || d.feature, { x: x + 0.12, y, w: 1.45, h: 0.34, fontFace: BF, fontSize: 10, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
      s.addShape(pres.shapes.RECTANGLE, { x: x + 1.6, y: y + 0.07, w, h: 0.2, fill: { color: up ? RED : TEAL }, line: { color: up ? RED : TEAL } }); });
    s.addText("Red bars raise the score; teal bars lower it", { x: x + 0.12, y: 3.5, w: 2.66, h: 0.22, fontFace: BF, fontSize: 10, italic: true, color: MUTED, margin: 0, isTextBox: true });
    s.addText(p[3], { x: x + 0.12, y: 3.78, w: 2.66, h: 1.25, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  });
  footer(s, "Source: explainability_results.json. Cases picked by a fixed rule, not by appearance. Identifiers and dates withheld.");
  s.addNotes("The cases were selected by a documented deterministic rule: A is the true positive whose score is nearest the median of true positives, C is the most confident false positive, D is the least confident false negative. Two of the three are errors on purpose, so the slide does not show only successes. Bars show SHAP contributions on the log-odds scale; red pushes the score up, teal down. Case C shows a limit: the model reads a long silence against a short earlier gap as a warning, but a customer can return for seasonal or other reasons that purchase history cannot reveal. Case D is a loyal, high-value customer who stopped; nothing in their history signalled it. Explanations describe the model's reasoning, not why the customer actually behaved as they did. The dashboard shows two more cases (typical retained customer and a borderline case). Customer identifiers and dates are withheld and profile values are rounded.");
}

// ------------------------------------------------------------------------------------------------ 8 What-if
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Adding purchases lowers the score, which shows model sensitivity, not a cure");
  const ks = [0, 1, 2, 3, 4, 5, 6].map(String); const A = W.cases.A_typical_true_positive.scores_by_extra_invoices, Cc = W.cases.C_confident_false_positive.scores_by_extra_invoices;
  s.addChart(pres.charts.LINE, [{ name: "Case A (typical flag)", labels: ks, values: A }, { name: "Case C (false alarm)", labels: ks, values: Cc }, { name: `Flag threshold ${f3(M.threshold)}`, labels: ks, values: ks.map(() => M.threshold) }],
    { x: 0.4, y: 1.1, w: 5.6, h: 3.95, ...chartBase("Risk score if the customer had made extra purchases"), showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: BF, chartColors: [TEAL, AMBER, SLATE], lineSize: 3, lineDataSymbolSize: 7,
      valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0", catAxisTitle: "Extra invoices (latest purchase 90 days before the prediction date)", showCatAxisTitle: true, catAxisTitleFontSize: 10 });
  s.addText("What you can explore live", { x: 6.2, y: 1.1, w: 3.3, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, ["Pick an example profile, add 0 to 6 invoices and choose when the latest purchase happened.", "Dependent figures (revenue, counts, ratios) are recalculated.", "Both scores come from the live Module 4 API."], 6.2, 1.45, 3.3, 1.7, 12, TEXT, 4);
  card(s, 6.2, 3.2, 3.3, 1.85, "FBEFD9", "Caution card");
  s.addText([{ text: "Not a causal test. ", options: { bold: true } }, { text: "Tenure, product breadth, cancellations and country stay fixed. A lower score does not guarantee a changed real-world outcome, and nothing personal is changed." }], { x: 6.3, y: 3.25, w: 3.1, h: 1.75, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  footer(s, `Live dashboard: ${URL}   |   Scores from the Module 4 API, model v${W.model_version}`);
  s.addNotes(`The chart was produced by sending each scenario to the Module 4 API code, not by hand. Case A (a typical flagged customer) falls below the threshold at three extra invoices (score ${A[3].toFixed(3)}, matching the Module 4 counterfactual search, which found three extra invoices with the latest purchase 90 days before the prediction date). Case C needs six extra invoices at this recency to fall below it (score ${Cc[6].toFixed(3)} at six; ${Cc[5].toFixed(3)} at five). The scenario adds invoices at the customer's own average order value, keeps revenue and count windows nested and recomputes the recency-to-gap ratio. Module 4 found that ${pct(E.counterfactuals.batch.feasible_share)} of ${E.counterfactuals.batch.n_flagged_sampled} sampled flagged customers could fall below the threshold within six extra invoices, with a median of ${E.counterfactuals.batch.median_extra_invoices}. Key limitation: this is model sensitivity. Making a real customer buy more would not necessarily change their risk the same way, and no protected or immutable characteristic is varied. Sensitivity tests also show that noise in revenue and shifts in recency of up to 7 days change test AUC by about 0.001 or less.`);
}

// ------------------------------------------------------------------------------------------------ 9 Fairness
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "UK and non-UK flag rates are similar, but non-UK false alarms run higher");
  card(s, 0.5, 1.05, 9, 0.5, "F6DDE0", "Warning banner");
  s.addText("No protected attributes exist in this data and none were inferred. This is an operational UK vs non-UK comparison, not proof that the model is fair.", { x: 0.6, y: 1.05, w: 8.8, h: 0.5, fontFace: BF, fontSize: 12, bold: true, color: RED, margin: 0, valign: "middle", isTextBox: true });
  const mets = ["Flag rate", "Lapsers caught", "False-alarm rate"];
  s.addChart(pres.charts.BAR, [{ name: `UK (n = ${n(T.UK.n)})`, labels: mets, values: [T.UK.selection_rate, T.UK.tpr, T.UK.fpr] }, { name: `Non-UK (n = ${n(T["Non-UK"].n)})`, labels: mets, values: [T["Non-UK"].selection_rate, T["Non-UK"].tpr, T["Non-UK"].fpr] }],
    { x: 0.4, y: 1.6, w: 4.7, h: 3.5, barDir: "col", ...chartBase("Outcomes by group on the test period"), showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: BF, chartColors: [TEAL, AMBER], showValue: true, dataLabelFormatCode: "0%", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0%", barGapWidthPct: 50 });
  const rows = [["Measure", "Value (95% interval)", "Status"],
    ["Disparate impact ratio", `${f3(C.disparate_impact_ratio)} (${f3(C.ci_disparate_impact_ratio[0])} to ${f3(C.ci_disparate_impact_ratio[1])})`, "Within band"],
    ["Flag-rate gap", `${C.demographic_parity_difference >= 0 ? "+" : ""}${f3(C.demographic_parity_difference)} (${f3(C.ci_demographic_parity_difference[0])} to ${f3(C.ci_demographic_parity_difference[1])})`, "Includes 0"],
    ["Lapsers-caught gap", `${f3(C.tpr_difference)} (${f3(C.ci_tpr_difference[0])} to ${f3(C.ci_tpr_difference[1])})`, "Within band"],
    ["False-alarm gap", `+${f3(C.fpr_difference)} (${f3(C.ci_fpr_difference[0])} to ${f3(C.ci_fpr_difference[1])})`, "Outside band"]];
  s.addTable(rows.map((r, i) => r.map((t, j) => ({ text: t, options: { bold: i === 0 || (i === 4 && j === 2), color: i === 0 ? WHITE : (i === 4 && j === 2 ? RED : TEXT), fill: { color: i === 0 ? NAVY : (i % 2 ? LIGHT : WHITE) }, fontSize: 10.5, fontFace: BF, valign: "middle" } }))),
    { x: 5.25, y: 1.65, w: 4.25, colW: [1.3, 1.95, 1.0], rowH: 0.34, border: { type: "solid", color: "D9E0E4", pt: 0.5 }, margin: 0.05 });
  s.addText([{ text: "Mitigation tried: ", options: { bold: true } }, { text: "group-specific thresholds and reweighing. Neither closed the gap, and the thresholds also cut recall to 0.755, so neither was adopted. Only the UK and Germany have 100+ test snapshots among countries." }],
    { x: 5.25, y: 3.95, w: 4.25, h: 1.2, fontFace: BF, fontSize: 11.5, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  footer(s, "Source: Fairness Metrics Report; final_test_results.json; equalised-odds framing after Hardt et al. (2016). Bands (DI 0.80-1.25; rates within 10% of overall) are governance thresholds, not legal tests.");
  s.addNotes(`Which groups and why: the dataset has no age, sex, ethnicity, disability or similar attribute and none were inferred. Country is the only demographic-like field. UK versus non-UK is therefore an operational grouping, with UK as the reference group (n = ${n(T.UK.n)}) and non-UK as the comparison (n = ${n(T["Non-UK"].n)}). The positive prediction is a flag for retention outreach, which can be a benefit (an offer) or a burden (unwanted contact), so both flag rates and error rates matter. Metrics: disparate impact ratio is the non-UK flag rate divided by the UK flag rate; demographic parity difference is the gap in flag rates; the equalised-odds view uses the gaps in lapsers caught (true positive rate) and false-alarm rate. Findings: flag rates are similar (ratio ${f3(C.disparate_impact_ratio)}) and lapsers are caught at similar rates, but non-UK customers who kept buying were flagged more often (false-alarm rate ${pct(T["Non-UK"].fpr)} vs ${pct(T.UK.fpr)}; ratio to overall ${f3(C.fpr_vs_overall)}), outside the Module 1 band of 0.90 to 1.10. The interval is wide because only ${T["Non-UK"].n} snapshots are non-UK. Mitigation actually performed: Fairlearn ThresholdOptimizer and Kamiran-Calders reweighing; neither fixed the gap on the test period, the group thresholds also reduced recall to 0.755, and the test numbers are exploratory because the disparity was first seen on test data. We describe results as within or outside the project's stated threshold; we do not claim the model is fair or legally compliant. The protected-attribute requirement cannot be assessed with this data, and an instructor clarification request is drafted.`);
}

// ------------------------------------------------------------------------------------------------ 10 Limitations, transparency, ethics
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "The model is a ranking aid for people to review, not a decision-maker");
  const cols = [["What it can do", TEAL, ["Rank active customers by relative risk of going quiet for 90 days", "Beat a simple recency rule on held-out data", "Show which behaviours move a score"]],
                ["What it cannot do", RED, ["Say why a customer will leave, or that a campaign will keep them", "Give guaranteed probabilities (not recalibrated; lapse rate moved 57% to 42%)", "Assess fairness for protected groups (none in the data)", "Predict for new, unidentified or long-inactive customers"]],
                ["Safeguards", NAVY, ["A person reviews every list before any contact", "No automated offers, exclusions or pricing", "Customers pseudonymised, which is not anonymous; API logs no request bodies", "Monitoring plan with review triggers (PROPOSED)"]]];
  cols.forEach((c, i) => { const x = 0.5 + i * 3.05; card(s, x, 1.1, 2.9, 3.6, LIGHT, "Column card");
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.1, w: 2.9, h: 0.5, fill: { color: c[1] }, line: { color: c[1] } });
    s.addText(c[0], { x: x + 0.12, y: 1.1, w: 2.66, h: 0.5, fontFace: HF, fontSize: 15, bold: true, color: WHITE, margin: 0, valign: "middle", isTextBox: true });
    bullets(s, c[2], x + 0.12, 1.72, 2.66, 3.3, 12, TEXT, 5); });
  footer(s, "Source: Model Card sections 2, 7-9 (after Mitchell et al., 2019); Ethics and privacy controls; Module 1 Ethical AI Charter");
  s.addNotes("Transparency statement. Intended use: rank currently active, identified customers to support human-reviewed retention planning. Not for: automated decisions about individuals (credit terms, exclusions, pricing), unidentified customers, customers inactive for more than 180 days, or inferring personal characteristics. Human oversight: a person reviews each list; the AI Ethics Committee owns the model-bias risk in the Module 2 RAID log; review triggers in the monitoring plan are proposals, not agreed controls. Privacy: customer keys are pseudonymised with a keyed hash, which is pseudonymous and not anonymous; the API accepts model-ready features only, rejects identifiers, and never logs request bodies. Other limitations: the 90-day window is proposed; the test set was scored twice plus exploratory runs; weaker on customers unseen in training (AUC 0.688); one test window and no drift evidence yet. Likely question: is this GDPR-compliant? This deck makes no compliance claim; lawful basis, DPIA and consent are organisational decisions outside the code.");
}

// ------------------------------------------------------------------------------------------------ 11 Business implications and next questions
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "What the results imply for retention planning, and what is still unknown");
  s.addText("Implications to weigh (hypotheses)", { x: 0.5, y: 1.1, w: 4.4, h: 0.5, fontFace: HF, fontSize: 14, bold: true, color: TEAL, margin: 0, isTextBox: true });
  bullets(s, [`List size sets the balance: the top 20% is ${pct(op20.precision, 0)} precise but catches ${pct(op20.recall, 0)}; the default list catches ${pct(L.recall, 0)} at ${pct(L.precision, 0)} precision.`,
              `${n(L.fp)} false alarms against ${n(L.fn)} misses: the cost of an unneeded offer versus a lost customer decides which matters more. Neither cost is measured.`,
              "Any gain toward the Module 1 target of +5 points in repeat purchases is a hypothesis; no measured retention or revenue effect exists.",
              "Non-UK customers may receive more unneeded outreach until the false-alarm gap is understood."], 0.5, 1.6, 4.4, 3.5, 12, TEXT, 6);
  card(s, 5.1, 1.1, 4.4, 3.95, PALE, "Questions card");
  s.addText("Questions for further analysis", { x: 5.25, y: 1.17, w: 4.1, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, ["Does a 90-day window match how this retailer's customers really buy?", "What does a false alarm cost, and what is a retained customer worth?", "Does contacting flagged customers change behaviour? That needs a controlled comparison, not this model.", "Does the non-UK false-alarm gap persist on newer data and larger samples?", "How will scores drift as the lapse rate changes?"], 5.25, 1.6, 4.1, 3.4, 12, TEXT, 6);
  footer(s, "Source: slides 4-9; Module 1 goals table; Model Card monitoring plan (PROPOSED)");
  s.addNotes("This slide explains implications and possible next analytical steps without prescribing a course of action. Every benefit statement is framed as a hypothesis because the project measured no operational or financial impact: there is no campaign data, no offer cost and no customer value in the dataset (Module 1 notes the data has no unit costs or demographics). The retention goal of five percentage points more repeat purchases is a Module 1 target, not a result. The questions on the right are the analysis that would turn the model's ranking into a business case: a window check with Marketing, a cost model, a controlled test of outreach, a re-check of the fairness gap on more data, and drift monitoring. Likely question: so should we use it? This deck gives you the evidence and the open questions; it does not make that decision.");
}

// ------------------------------------------------------------------------------------------------ 12 Dashboard and references
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Explore the model yourself on the live dashboard");
  s.addImage({ path: path.join(__dirname, "qr_dashboard.png"), x: 0.5, y: 1.15, w: 1.9, h: 1.9, altText: "QR code linking to the live dashboard" });
  s.addText(URL, { x: 2.6, y: 1.2, w: 6.9, h: 0.4, fontFace: BF, fontSize: 15, bold: true, color: TEAL, margin: 0, isTextBox: true, hyperlink: { url: URL, tooltip: "Open the live dashboard" } });
  bullets(s, ["Business overview with filters (month, UK or non-UK)", "Results and explanations, including five held-out cases", "Prediction and what-if explorer (calls the live API)", "Fairness and ethics view with definitions and limits", "About and evidence: provenance, limits, links"], 2.6, 1.65, 6.9, 1.5, 12, TEXT, 2);
  tag(s, 0.5, 3.12, 1.9, VERIFIED ? `Verified ${VERIFIED}` : "Deployment not yet verified", VERIFIED ? "2E8B57" : AMBER);
  s.addText("References", { x: 0.5, y: 3.5, w: 9, h: 0.28, fontFace: HF, fontSize: 13, bold: true, color: NAVY, margin: 0, isTextBox: true });
  // APA 7 (same as NXU style). Each entry: [plain text before italic, italic part, plain text after]
  const refs = [
    ["Chen, D. (2019). ", "Online Retail II", " [Data set]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D"],
    ["Hardt, M., Price, E., & Srebro, N. (2016). Equality of opportunity in supervised learning. ", "Advances in Neural Information Processing Systems, 29", ", 3315\u20133323."],
    ["Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. ", "Knowledge and Information Systems, 33", "(1), 1\u201333. https://doi.org/10.1007/s10115-011-0463-8"],
    ["Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. ", "Advances in Neural Information Processing Systems, 30", ", 4765\u20134774."],
    ["Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. ", "Proceedings of the Conference on Fairness, Accountability, and Transparency", ", 220\u2013229. https://doi.org/10.1145/3287560.3287596"],
    ["Weerts, H., Dudík, M., Edgar, R., Jalali, A., Lutz, R., & Madaio, M. (2023). Fairlearn: Assessing and improving fairness of AI systems. ", "Journal of Machine Learning Research, 24", "(257), 1\u20138."]];
  const runs = [];
  refs.forEach((r, k) => { r.forEach((seg, j) => runs.push({ text: seg, options: { italic: j === 1, breakLine: j === 2 && k < refs.length - 1, paraSpaceAfter: 2 } })); });
  s.addText(runs, { x: 0.5, y: 3.78, w: 9, h: 1.55, fontFace: BF, fontSize: 8, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  s.addNotes(`The dashboard link and QR code point to ${URL}. ${VERIFIED ? "The live deployment was opened and checked on " + VERIFIED + "." : "At the time this deck was built the live deployment had not been independently verified, so the status tag says so; the deck should be rebuilt with the verified date once checked."} The dashboard is a Streamlit app on a Hugging Face Docker Space; the same container runs the Module 4 FastAPI service on its loopback interface and the dashboard calls it for live predictions. It stores aggregate evidence only. Source code and documents: ${REPO}. References follow APA 7, the style Nexford uses, and are the same entries as the Module 4 report reference list. In text the deck cites Chen (2019) for the data, Hardt et al. (2016) for equalised odds, Lundberg and Lee (2017) for SHAP, Mitchell et al. (2019) for model cards, Kamiran and Calders (2012) for reweighing and Weerts et al. (2023) for Fairlearn. Chen and Kamiran and Calders were checked in Module 4; the others were carried over from the Module 4 list and have not been re-checked against publisher pages in this session.`);
}

// ------------------------------------------------------------------------------------------------ 13 Appendix: validation and data
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Appendix A. Validation and data provenance");
  const rows = [["Split", "Prediction dates", "Rows", "Customers", "Lapse rate"], ["Train", "Jun-Dec 2010", "20,584", "4,225", "0.483"], ["Validation", "Mar-Apr 2011", "6,637", "3,584", "0.569"], ["Test", "Aug-Sep 2011", n(M.test_rows), n(M.test_customers), f3(M.prevalence)]];
  s.addTable(rows.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: i === 0 ? WHITE : TEXT, fill: { color: i === 0 ? NAVY : (i % 2 ? LIGHT : WHITE) }, fontSize: 11, fontFace: BF } }))), { x: 0.5, y: 1.1, w: 5.0, colW: [1.0, 1.4, 0.8, 0.9, 0.9], rowH: 0.3, border: { type: "solid", color: "D9E0E4", pt: 0.5 }, margin: 0.04 });
  bullets(s, ["Time-ordered splits with a 90-day purge between them; no customer-snapshot's outcome window overlaps the next split", "Tuning: 4-fold expanding-window CV, 3-month purge, 25 random draws, ROC-AUC; preprocessing fitted inside each fold", "Selection rule fixed in advance: best validation AUC; prefer a simpler model within 0.005; then a fairness gate", `Threshold ${f3(M.threshold)} maximises F1 on validation, not on test`, "Label: no sales invoice in the 90 days after T; eligibility: invoice in the 180 days before T (PROPOSED). Incomplete follow-up is never labelled churn"], 0.5, 2.5, 5.0, 2.7, 11, TEXT, 3);
  s.addText("Baselines and metrics", { x: 5.8, y: 1.1, w: 3.7, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const mr = [["Test metric", "Model", "Recency rule"], ["ROC-AUC", f3(L.roc_auc), f3(B.roc_auc)], ["PR-AUC", f3(L.pr_auc), f3(B.pr_auc)], ["Precision", f3(L.precision), f3(B.precision)], ["Recall", f3(L.recall), f3(B.recall)], ["F1", f3(L.f1), f3(B.f1)], ["Brier", f3(L.brier), f3(B.brier)]];
  s.addTable(mr.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: i === 0 ? WHITE : TEXT, fill: { color: i === 0 ? NAVY : (i % 2 ? LIGHT : WHITE) }, fontSize: 11, fontFace: BF } }))), { x: 5.8, y: 1.45, w: 3.7, colW: [1.3, 1.1, 1.3], rowH: 0.28, border: { type: "solid", color: "D9E0E4", pt: 0.5 }, margin: 0.04 });
  bullets(s, ["Recency rule flags 95% of customers (threshold 1/36), so its recall is high and precision low", "Provenance: Module 3 fact table; dataset hash " + M.dataset_hash + "; MLflow run " + M.mlflow.test_run_id.slice(0, 8) + "; registry " + M.registry.registered_model + " v" + M.registry.version, "Test set scored twice (AUC 0.767 then 0.765) plus exploratory mitigation runs: disclosed"], 5.8, 3.55, 3.7, 1.7, 10.5, TEXT, 3);
  footer(s, "Source: Validation Report sections 2-4 and 7; Model Card; reports/model/*.json");
  s.addNotes("Backup for questions on validation. Why time-ordered splits: random splits would let the model learn from the future. The purge keeps outcome windows from overlapping the next split. Cross-validation is expanding-window with a three-month purge. The test period was never used to tune the model, but it was scored twice because iteration 1 had exactly collinear windows and fragile missing-value indicators found by a collinearity check; iteration 2 removed them, and AUC moved from 0.767 to 0.765. Exploratory mitigation runs also computed test results. The recency-rule baseline (longer since last purchase, higher risk) flags almost everyone, so its high recall is not useful. Brier score checks probability accuracy: 0.193 for the model against 0.246 for the baseline. Metric definitions: precision = TP/(TP+FP); recall = TP/(TP+FN); F1 is their harmonic mean; ROC-AUC is the chance a random lapser scores above a random stayer.");
}

// ------------------------------------------------------------------------------------------------ 14 Appendix: explainability and fairness
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Appendix B. Explainability and fairness details");
  s.addText("Explainability", { x: 0.5, y: 1.05, w: 4.4, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: TEAL, margin: 0, isTextBox: true });
  bullets(s, ["SHAP LinearExplainer on the log-odds scale; 500 training background rows, 2,000 test rows", "Counterfactuals: grid of 6 invoice counts x 6 recency values on mutable behaviour only; every result re-scored through the pipeline", `${pct(E.counterfactuals.batch.feasible_share)} of 300 flagged customers fall below the threshold within 6 extra invoices; median ${E.counterfactuals.batch.median_extra_invoices}`, "Sensitivity: revenue noise (sigma 0.1 to 0.2) and recency shifts of 3 to 7 days move AUC by 0.001 or less; 20% random missingness in five features lowers it by 0.006", "LIME was not run; DiCE and Alibi were not used because the search space is only 36 scenarios"], 0.5, 1.4, 4.4, 3.8, 11, TEXT, 3);
  s.addText("Fairness", { x: 5.1, y: 1.05, w: 4.4, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: TEAL, margin: 0, isTextBox: true });
  bullets(s, ["Disparate impact ratio: non-UK flag rate / UK flag rate; accepted band 0.80 to 1.25 (Module 2)", "Demographic parity difference: gap in flag rates", "Equalised odds: gaps in true-positive and false-positive rates; each within 10% of overall (Module 1)", `Samples: UK ${n(T.UK.n)}, non-UK ${n(T["Non-UK"].n)}; minimum 100 per group for a reliable comparison`, "Mitigation (test numbers exploratory): false-alarm gap 0.086 with reweighing and 0.080 with group thresholds, versus 0.075 unmitigated; thresholds also cut recall to 0.755", "Country as a feature changes validation AUC by 0.0002, so it is excluded", `Segment audit (behavioural, not protected): the fixed threshold flags ${pct(E.segment_audit.dimensions.frequency_tier.tiers.Low.flag_rate)} of customers with two or fewer invoices, so inside that tier the flag does not separate lapsers from stayers`], 5.1, 1.4, 4.4, 3.8, 10.5, TEXT, 3);
  footer(s, "Source: explainability_results.json; mitigation_results.json; ablation_country_flag.json; Fairness Metrics Report");
  s.addNotes("Backup for technical questions. SHAP LinearExplainer is exact for a linear model; values are on the log-odds scale. A LightGBM cross-check agrees on 3 of the top 5 features. The segment audit groups customers by tenure, spend and purchase frequency (tertiles fixed on training data); these are behavioural segments, not demographic or protected groups, and the audit is exploratory and descriptive. The counterfactual method reuses Module 4: it varies only extra invoices (up to six) and the date of the latest purchase, keeps windows nested, and recomputes dependent ratios. Mitigation figures: unmitigated non-UK minus UK false-positive-rate gap on test is 0.075; reweighing gives 0.086 and the equalised-odds threshold optimiser 0.080; recall falls from 0.881 to 0.755 under the optimiser. Definitions are plain-language and only the metrics supported by the analysis are used. Protected attributes were unavailable; the UK vs non-UK analysis is supplementary and does not satisfy a protected-attribute requirement. Instructor clarification request is drafted and unsent.");
}

// ------------------------------------------------------------------------------------------------ 15 Appendix: technical demo
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Appendix C. Technical demonstration and reproducibility");
  box(s, 0.5, 1.15, 1.6, 0.6, "Browser", SLATE, WHITE, 12); box(s, 2.5, 1.15, 2.2, 0.6, "Streamlit dashboard\n(port 7860)", TEAL, WHITE, 11); box(s, 5.1, 1.15, 2.3, 0.6, "FastAPI /predict\n(loopback :8000)", NAVY, WHITE, 11); box(s, 7.8, 1.15, 1.7, 0.6, "Model v1.0.0\n(joblib)", AMBER, TEXT, 11);
  arrow(s, 2.12, 1.45, 2.48, 1.45); arrow(s, 4.72, 1.45, 5.08, 1.45); arrow(s, 7.42, 1.45, 7.78, 1.45);
  s.addText("One Hugging Face Docker Space runs both processes. The API is reachable only from the dashboard, not from the public internet.", { x: 0.5, y: 1.85, w: 9, h: 0.3, fontFace: BF, fontSize: 11, italic: true, color: MUTED, margin: 0, isTextBox: true });
  card(s, 0.5, 2.25, 4.5, 2.85, "F4F6F8", "Code card");
  s.addText("Request (model-ready features, no identifiers)\nPOST /predict\n{ \"recency_days\": 40, \"tenure_days\": 400, \"n_inv_all\": 6,\n  \"n_inv_30\": 0, \"n_inv_90\": 1, \"n_inv_prev90\": 2,\n  \"rev_all\": 1800.5, \"rev_90\": 300, \"rev_180\": 900,\n  \"n_products_all\": 60, \"n_products_180\": 35,\n  \"avg_units_per_inv\": 120, \"mean_gap_days\": 55,\n  \"std_gap_days\": 20, \"recency_over_gap\": 0.73,\n  \"n_cancel_all\": 0, \"cancel_ratio\": 0 }", { x: 0.6, y: 2.3, w: 4.3, h: 2.75, fontFace: "Courier New", fontSize: 9, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  card(s, 5.2, 2.25, 4.3, 1.45, "F4F6F8", "Code card");
  s.addText("Response (200)\n{ \"model_version\": \"1.0.0\", \"churn_probability\": 0.317697,\n  \"flagged_high_churn_risk\": true,\n  \"decision_threshold\": 0.313903, \"imputed_fields\": [] }\nInvalid input -> 422; values never echoed", { x: 5.3, y: 2.3, w: 4.1, h: 1.35, fontFace: "Courier New", fontSize: 9, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  s.addText([{ text: "Run it: ", options: { bold: true } }, { text: "PYTHONPATH=src uvicorn churn_model.api:app --port 8000, then python scripts/api_demo.py --check-parity. Dashboard: streamlit run dashboard/app.py. " }, { text: "Code: ", options: { bold: true } }, { text: REPO }],
    { x: 5.2, y: 3.8, w: 4.3, h: 1.3, fontFace: BF, fontSize: 10.5, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  footer(s, `Model v${M.model_version} | sha-256 ${M.model_sha256_16}... | registry ${M.registry.registered_model} v${M.registry.version} | pinned requirements: requirements-ml.txt, dashboard/requirements.txt`);
  s.addNotes("The API demo script (scripts/api_demo.py) runs against a local API and checks six expectations: health, model info, a valid request, a scenario request, an invalid request that returns 422 without echoing values, and an unknown-field request carrying an identifier that is refused. With --check-parity it also confirms the API score equals the serialised model scored directly to six decimals. The captured output is in reports/evidence/api_demo_output.txt. The shown response is the verified output of that run. In the hosted dashboard the same API runs inside the Space container on its loopback interface; the dashboard calls it for each live prediction and shows an explicit error, never a stored score, if the API is unreachable. Architecture limit: the public internet cannot call the API directly, so the demo script is run locally against the same code. Docker image build was not tested in the development sandbox; the same files were run in a fresh pinned virtual environment through the same start script.");
}

(async () => {
  const out = path.join(__dirname, "Module5_Churn_Insights.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
