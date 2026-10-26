// Builds the 12-slide Module 3 deck from measured results (deck/data.json, produced from reports/latest + reports/evidence).
// Usage: node deck/build_deck.js  -> deck/Module3_Retail_Pipeline.pptx
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/root/.claude/skills/synced/afbd2cd8-330c-4bdc-ba57-b498a7c52ff0_bad5ed0e-07a5-4673-805c-226b568cdf11/pptx/scripts/apply_theme.js");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));
const n = (x) => Number(x).toLocaleString("en-GB");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";

const THEME = {
  name: "RetailPipeline", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B2A38", lt1: "FFFFFF", dk2: "12344D", lt2: "EEF3F5", accent1: "1C7C7D", accent2: "F2A541",
            accent3: "D95D39", accent4: "2E8B57", accent5: "6C7A89", accent6: "8FB8DE", hlink: "1C7C7D", folHlink: "6C7A89" },
};
const NAVY = "12344D", TEXT = "1B2A38", TEAL = "1C7C7D", AMBER = "F2A541", CORAL = "D95D39", GREEN = "2E8B57", SLATE = "6C7A89",
      LIGHT = "EEF3F5", WHITE = "FFFFFF", SKY = "8FB8DE", MUTED = "5B6B79";
const HF = "Cambria", BF = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: HF, bodyFontFace: BF };
pres.title = "Retail Analytics Decision Support Platform - Module 3 pipeline";
pres.author = "Bezzel Chitsungo";

pres.defineSlideMaster({
  title: "CONTENT", background: { color: WHITE },
  slideNumber: { x: 9.1, y: 5.28, w: 0.5, h: 0.25, fontFace: BF, fontSize: 10, color: MUTED, align: "right" },
  objects: [],
});
pres.defineSlideMaster({ title: "DARK", background: { color: NAVY } });

let figN = 0;
function header(s, title, sub) {
  s.addText(title, { x: 0.5, y: 0.28, w: 9, h: 0.55, fontFace: HF, fontSize: 28, bold: true, color: NAVY, margin: 0, isTextBox: true, objectName: "Title" });
  if (sub) s.addText(sub, { x: 0.5, y: 0.84, w: 9, h: 0.32, fontFace: BF, fontSize: 14, color: MUTED, margin: 0, isTextBox: true, objectName: "Subtitle" });
}
function footer(s, text) {
  s.addText(text, { x: 0.5, y: 5.28, w: 8.5, h: 0.25, fontFace: BF, fontSize: 10, color: MUTED, margin: 0, isTextBox: true, objectName: "Source" });
}
function card(s, x, y, w, h, fill = LIGHT, name = "Card") {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0.5 }, rectRadius: 0.08, objectName: name });
}
function stat(s, x, y, w, h, big, label, color = TEAL, fill = LIGHT) {
  card(s, x, y, w, h, fill, "Stat card");
  s.addText(big, { x: x + 0.1, y: y + 0.06, w: w - 0.2, h: h * 0.55, fontFace: HF, fontSize: 26, bold: true, color, margin: 0, valign: "middle", isTextBox: true });
  s.addText(label, { x: x + 0.1, y: y + h * 0.55, w: w - 0.2, h: h * 0.42, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", isTextBox: true });
}
function box(s, x, y, w, h, text, fill, color = WHITE, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: opts.line || fill, width: 1, dashType: opts.dash || "solid" }, rectRadius: 0.08, objectName: "Process step" });
  s.addText(text, { x, y, w, h, fontFace: BF, fontSize: opts.fs || 12, bold: opts.bold !== false, color, align: "center", valign: "middle", margin: 0.04, isTextBox: true });
}
function arrow(s, x1, y1, x2, y2, color = SLATE, dash = "solid") {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1, line: { color, width: 1.5, endArrowType: "triangle", dashType: dash }, objectName: "Arrow" });
}
function tag(s, x, y, w, text, color) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.24, fill: { color }, line: { color }, rectRadius: 0.05, objectName: "Status tag" });
  s.addText(text, { x, y, w, h: 0.24, fontFace: BF, fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
const chartBase = (title) => ({
  showTitle: true, title, titleFontSize: 12, titleFontFace: BF, titleColor: TEXT, showLegend: false,
  catAxisLabelFontSize: 11, catAxisLabelFontFace: BF, catAxisLabelColor: TEXT, valAxisLabelFontFace: BF, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED,
  dataLabelFontSize: 11, dataLabelFontFace: BF, dataLabelColor: TEXT, valGridLine: { style: "none" }, catGridLine: { style: "none" },
});

// ---------------------------------------------------------------------------------------------------------- 1 Title
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("Retail Analytics Decision Support Platform", { x: 0.6, y: 1.0, w: 5.6, h: 1.5, fontFace: HF, fontSize: 36, bold: true, color: WHITE, margin: 0, valign: "top", isTextBox: true, objectName: "Title" });
  s.addText("Module 3: a reproducible, validated and governed data pipeline for Online Retail II", { x: 0.6, y: 2.6, w: 5.4, h: 0.8, fontFace: BF, fontSize: 16, color: SKY, margin: 0, isTextBox: true, objectName: "Subtitle" });
  s.addText("Bezzel Chitsungo", { x: 0.6, y: 3.9, w: 5.4, h: 0.4, fontFace: BF, fontSize: 20, bold: true, color: WHITE, margin: 0, isTextBox: true });
  s.addText("MSc Data Analytics, Nexford University  |  BAN 6800", { x: 0.6, y: 4.32, w: 5.4, h: 0.35, fontFace: BF, fontSize: 14, color: SKY, margin: 0, isTextBox: true });
  const items = [[n(D.rows), "raw transaction lines profiled and reconciled"], [String(D.val.bronze.expectations_evaluated + D.val.outputs.expectations_evaluated), "Great Expectations checks, all passed"], [String(D.tests), "automated tests passed"]];
  items.forEach((it, i) => {
    const y = 1.0 + i * 1.35;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.5, y, w: 3.0, h: 1.15, fill: { color: "1B4A6B" }, line: { color: "1B4A6B" }, rectRadius: 0.1, objectName: "Stat card" });
    s.addText(it[0], { x: 6.65, y: y + 0.08, w: 2.7, h: 0.55, fontFace: HF, fontSize: 30, bold: true, color: AMBER, margin: 0, isTextBox: true });
    s.addText(it[1], { x: 6.65, y: y + 0.64, w: 2.7, h: 0.45, fontFace: BF, fontSize: 12, color: WHITE, margin: 0, isTextBox: true });
  });
  s.addNotes("Title slide. This capstone continues the Retail Analytics Decision Support Platform from Modules 1 and 2 and delivers an executed, reproducible pipeline for the Online Retail II data (Chen, 2019; UCI Machine Learning Repository). All figures in this deck come from the executed run recorded in reports/latest and reports/evidence in the repository.");
}

// ---------------------------------------------------------------------------------------------------------- 2 Business problem
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Business problem and continuity", "One gap: transaction data is not turned into timely, governed decisions");
  const cols = [
    ["Module 1  Vision", ["UK giftware retailer; spreadsheet reporting", "Forecasting, RFM, churn, inventory goals", "Ethical AI Charter: fairness, privacy"], SLATE],
    ["Module 2  Blueprint", ["Azure architecture and Privacy Plan", "Agile plan, RAID log, fairness metrics", "Keyed-hash Customer ID, zoned storage"], SLATE],
    ["Module 3  This pipeline", ["Executable DAG on the real file", "Validation, bias, privacy, audit", "Governed tables for every user group"], TEAL],
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i * 3.1;
    card(s, x, 1.35, 2.8, 1.85, c[2] === TEAL ? "DCEFEF" : LIGHT, "Phase card");
    s.addText(c[0], { x: x + 0.15, y: 1.42, w: 2.5, h: 0.36, fontFace: HF, fontSize: 15, bold: true, color: c[2] === TEAL ? TEAL : NAVY, margin: 0, isTextBox: true });
    s.addText(c[1].map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < c[1].length - 1 } })), { x: x + 0.15, y: 1.82, w: 2.55, h: 1.3, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", paraSpaceAfter: 4, isTextBox: true });
    if (i < 2) arrow(s, x + 2.82, 2.2, x + 3.08, 2.2, TEAL);
  });
  s.addText("Who uses the outputs, and which decision they support", { x: 0.5, y: 3.38, w: 9, h: 0.3, fontFace: BF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const users = [["Finance and leaders", "Daily revenue by country", "Investment"], ["Inventory and Procurement", "Weekly SKU demand", "Reorder quantities"], ["Marketing", "RFM base per customer", "Campaign design"], ["E-commerce and Operations", "Sales and cancellations", "Merchandising"]];
  users.forEach((u, i) => {
    const x = 0.5 + i * 2.28;
    card(s, x, 3.75, 2.1, 1.35, WHITE, "User card");
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.75, w: 2.1, h: 1.35, fill: { color: WHITE }, line: { color: SKY, width: 1 }, rectRadius: 0.08 });
    s.addText(u[0], { x: x + 0.1, y: 3.81, w: 1.9, h: 0.5, fontFace: BF, fontSize: 12, bold: true, color: NAVY, margin: 0, valign: "top", isTextBox: true });
    s.addText(u[1], { x: x + 0.1, y: 4.3, w: 1.9, h: 0.3, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, isTextBox: true });
    s.addText("-> " + u[2], { x: x + 0.1, y: 4.67, w: 1.9, h: 0.3, fontFace: BF, fontSize: 12, bold: true, color: TEAL, margin: 0, isTextBox: true });
  });
  footer(s, "Sources: Module 1 Vision Document; Module 2 Business Analytics Project Overview Report (14 Oct 2026)");
  s.addNotes("Continuity: the business problem, dataset, stakeholders, technology stack and Ethical AI Charter are carried forward unchanged from Modules 1 and 2. Module 2 produced the Azure-based architecture and Data Privacy Plan; Module 3 turns them into running controls. The only change is the orchestration framework: Prefect is used for an executable open-source DAG, with Azure Data Factory remaining the proposed production equivalent. Each stakeholder group on this slide is fed by a specific published table (slide 7).");
}

// ---------------------------------------------------------------------------------------------------------- 3 Data and inputs
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Actual data and inputs", "Real file, verified size; no synthetic records were needed");
  stat(s, 0.5, 1.35, 2.1, 1.1, n(D.rows), "rows (requirement: at least 5,000)", TEAL);
  stat(s, 2.75, 1.35, 1.6, 1.1, "8", "source fields", NAVY);
  stat(s, 0.5, 2.6, 2.1, 1.1, String(D.countries), "countries recorded", NAVY);
  stat(s, 2.75, 2.6, 1.6, 1.1, n(D.distinct_customers), "distinct Customer IDs", NAVY);
  stat(s, 0.5, 3.85, 3.85, 1.2, pct(D.miss["Customer ID"] / D.rows, 2), "of rows have no Customer ID (" + n(D.miss["Customer ID"]) + "); kept as unidentified sales", CORAL);
  const rows = [
    ["Source", "Online Retail II (UCI dataset 502; Chen, 2019)"],
    ["Format and size", "CSV, " + (D.bytes / 1e6).toFixed(1) + " MB, SHA-256 " + D.sha.slice(0, 8) + "... pinned"],
    ["Grain", "One invoice line (product on an invoice)"],
    ["Coverage", "1 Dec 2009 to 9 Dec 2011 (last month partial)"],
    ["Source update frequency", "None: static historical snapshot"],
    ["Pipeline schedule (PROPOSED)", "Daily 02:00 UTC if a live feed replaces it; not deployed"],
    ["Data Dictionary", "8 source fields + 7 output tables; tests enforce it matches the real schemas"],
  ];
  const tbl = rows.map((r, i) => [
    { text: r[0], options: { bold: true, color: NAVY, fill: { color: LIGHT }, fontFace: BF, fontSize: 11, valign: "middle" } },
    { text: r[1], options: { color: TEXT, fill: { color: WHITE }, fontFace: BF, fontSize: 11, valign: "middle" } },
  ]);
  s.addTable(tbl, { x: 4.6, y: 1.35, w: 4.9, colW: [1.55, 3.35], rowH: 0.5, border: { type: "solid", pt: 0.5, color: "D5DEE3" }, margin: [0.03, 0.08, 0.03, 0.08], objectName: "Input facts" });
  footer(s, "Source: reports/latest/source_profile.json, ingestion_manifest.json (run-001); docs/data_dictionary.yaml");
  s.addNotes("Verified facts from the supplied file: 1,067,371 data rows and 8 fields, so the 5,000-record requirement is met by actual data and no synthetic records were generated. The source is one CSV; it contains no worksheet names, so the two source blocks were identified from a single backward step in InvoiceDate and then verified by record comparison (slide 5). The source itself never refreshes; the daily schedule shown is a proposal only. The Data Dictionary (docs/data_dictionary.yaml) lists source fields, types, nullability, constraints, sensitivity and derived fields, and a test fails if it disagrees with the real output schemas.");
}

// ---------------------------------------------------------------------------------------------------------- 4 Architecture
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Pipeline architecture", "Sources to published analytics, with gates that can stop publication");
  const w = 1.62, gap = 0.25, x0 = 0.45, h = 0.62;
  const colX = (i) => x0 + i * (w + gap);
  const A = [["Source CSV", SLATE], ["1 Ingest", NAVY], ["3 Validate bronze", AMBER], ["4 Clean +\npseudonymise", NAVY], ["5 Transform", NAVY]];
  A.forEach((a, i) => { box(s, colX(i), 1.4, w, h, a[0], a[1], a[1] === AMBER ? TEXT : WHITE); if (i < 4) arrow(s, colX(i) + w, 1.71, colX(i + 1), 1.71, SLATE); });
  // elbow from Transform down-left to Integrate
  s.addShape(pres.shapes.LINE, { x: colX(4) + w / 2, y: 2.02, w: 0, h: 0.33, line: { color: SLATE, width: 1.5 } });
  s.addShape(pres.shapes.LINE, { x: colX(0) + w / 2, y: 2.35, w: colX(4) - colX(0), h: 0, line: { color: SLATE, width: 1.5 } });
  arrow(s, colX(0) + w / 2, 2.35, colX(0) + w / 2, 2.6, SLATE);
  const B = [["6 Integrate\n(fact, dims, aggregates)", NAVY], ["7 Validate outputs\n(Great Expectations)", AMBER], ["10 Publish gate\n(atomic)", AMBER], ["Published Parquet\n+ manifest", GREEN]];
  B.forEach((b, i) => { box(s, colX(i), 2.6, w, 0.72, b[0], b[1], b[1] === AMBER ? TEXT : WHITE, { fs: 11 }); if (i < 3) arrow(s, colX(i) + w, 2.96, colX(i + 1), 2.96, SLATE); });
  // branches
  box(s, colX(1), 3.85, w, 0.62, "2 Profile source\n(branch of 1)", WHITE, TEAL, { line: TEAL, dash: "dash", fs: 11 });
  box(s, colX(2), 3.85, w, 0.62, "8 Bias detection\n(branch of 6)", WHITE, TEAL, { line: TEAL, dash: "dash", fs: 11 });
  box(s, colX(3), 3.85, w, 0.62, "9 Privacy scan\n(branch of 6; PII gate)", WHITE, TEAL, { line: TEAL, dash: "dash", fs: 11 });
  box(s, colX(4), 3.85, w, 0.62, "11 Evidence +\naudit log", WHITE, TEAL, { line: TEAL, dash: "dash", fs: 11 });
  // legend
  [["Processing", NAVY], ["Gate (blocks on critical failure)", AMBER], ["Governance branch", TEAL], ["Output", GREEN]].forEach((l, i) => {
    const lx = 0.5 + [0, 1.3, 4.2, 6.2][i];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: lx, y: 4.7, w: 0.2, h: 0.2, fill: { color: l[1] }, line: { color: l[1] }, rectRadius: 0.03 });
    s.addText(l[0], { x: lx + 0.27, y: 4.65, w: 2.7, h: 0.3, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  });
  s.addText("Module 2 mapping (proposed production): ADLS zones, ADF activities, Key Vault, Power BI", { x: 0.5, y: 4.98, w: 9, h: 0.28, fontFace: BF, fontSize: 11, italic: true, color: MUTED, margin: 0, isTextBox: true });
  footer(s, "Source: src/retail_pipeline/flow.py; docs/architecture.md");
  s.addNotes("The flow is implemented in Prefect, with task dependencies expressed through futures. It follows Sources, ingestion, cleaning, transformation, integration, validation and publication. Amber boxes are gates: the bronze gate stops cleaning, and the output gate plus the PII gate stop publication. The dashed teal boxes are parallel branches for profiling, bias detection, privacy scanning and evidence. Module 2 named Azure Data Factory; it cannot run locally or for free, so Prefect provides the executable DAG while each task maps to an ADF activity. That mapping is a deployment recommendation, not something executed here.");
}

// ---------------------------------------------------------------------------------------------------------- 5 Ingestion and profiling
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Ingestion and source profiling", "Raw data stays untouched; rules come from measured findings");
  card(s, 0.5, 1.35, 3.4, 2.55, LIGHT, "Provenance card");
  s.addText("Provenance (implemented)", { x: 0.65, y: 1.42, w: 3.1, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText([
    { text: "Raw CSV made read-only; SHA-256 pinned", options: { bullet: true, breakLine: true } },
    { text: "Bronze: all-text Parquet + row id, content-addressed", options: { bullet: true, breakLine: true } },
    { text: "0 parse failures in Quantity, Price, date, ID", options: { bullet: true, breakLine: true } },
    { text: "Run id, rules hash and code hash recorded", options: { bullet: true } },
  ], { x: 0.65, y: 1.78, w: 3.15, h: 2.05, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", paraSpaceAfter: 5, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.05, w: 3.4, h: 1.05, fill: { color: "FFF3DC" }, line: { color: AMBER, width: 1 }, rectRadius: 0.08, objectName: "Callout" });
  s.addText([{ text: "Overlap verified, not assumed. ", options: { bold: true } }, { text: n(D.overlap.rows_block2_in_window) + " rows (" + n(D.overlap.invoices_in_window_block2) + " invoices) in 1-9 Dec 2010 are identical in both source blocks." }],
    { x: 0.6, y: 4.1, w: 3.2, h: 0.95, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  const lab = ["Missing Customer ID", "Exact duplicate extra copies", "Negative quantity", "Verified overlap duplicates", "Cancellation ('C') lines", "Zero price", "Stock codes off 5-digit pattern"];
  const val = [D.miss["Customer ID"], D.dup_extra, D.neg_qty, D.overlap.rows_block2_in_window, D.canc_rows, D.zero_price, D.nonpattern_rows];
  s.addChart(pres.charts.BAR, [{ name: "Rows", labels: lab, values: val }], { x: 4.1, y: 1.3, w: 5.45, h: 3.85, barDir: "bar", chartColors: [TEAL, TEAL, TEAL, AMBER, TEAL, TEAL, TEAL], catAxisOrientation: "maxMin",
    valAxisHidden: true, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", barGapWidthPct: 45, ...chartBase("Measured quality findings (rows)"), valAxisMaxVal: 300000 });
  footer(s, "Source: reports/latest/source_profile.json, cleaning_summary.json (run-001); categories overlap, do not add");
  s.addNotes("Profiling ran before any cleaning rules were set, on the actual file. Findings: 243,007 rows lack a Customer ID, 34,335 extra exact-duplicate copies exist, 22,950 rows have negative quantity (19,493 on cancellation invoices and 3,457 on non-cancellation invoices), 6,202 rows have zero price and 5 have negative prices. The InvoiceDate column steps backward once (row 525,461). Rather than removing records because of that reset, the two blocks were compared record by record; the 22,523 rows in the overlap window were identical as multisets, so the second copies are treated as confirmed duplicate ingestion. Categories overlap, so the bars should not be added together. Limitation: the CSV has no worksheet names, so the block boundary is inferred.");
}

// ---------------------------------------------------------------------------------------------------------- 6 Cleaning
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Cleaning and transformation", "Every raw row gets one disposition and a reason code");
  stat(s, 0.5, 1.35, 2.6, 1.15, pct(D.disp.rows_retained / D.disp.rows_raw, 2), "retained: " + n(D.disp.rows_retained) + " lines", GREEN);
  const r = D.reasons;
  const labs = ["Overlap duplicates (excluded)", "Non-merchandise lines (excluded)", "Stock adjustments (quarantined)", "Zero price (quarantined)"];
  const vals = [r.EXC_DUP_OVERLAP, r.EXC_NON_MERCHANDISE, r.QRN_STOCK_ADJUSTMENT, r.QRN_ZERO_PRICE];
  s.addChart(pres.charts.BAR, [{ name: "Rows", labels: labs, values: vals }], { x: 0.4, y: 2.55, w: 4.5, h: 2.6, barDir: "bar", chartColors: [AMBER, AMBER, CORAL, CORAL], catAxisOrientation: "maxMin", valAxisHidden: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", barGapWidthPct: 40, valAxisMaxVal: 30000, ...chartBase("Rows not retained, by reason code") });
  const rows = [["Rule", "Evidence-based handling"],
    ["Verified overlap", "Drop 2nd copy only if blocks match exactly"],
    ["Ledger codes (POST, M, fees, vouchers)", "Excluded from product analytics"],
    ["Negative qty on non-C invoice", "Quarantine as stock adjustment"],
    ["Zero price", "Quarantine (no revenue)"],
    ["Cancellation 'C' with negative qty", "Retained: " + n(17974) + " valid return lines"],
    ["Exact duplicates in one block", "Retained and flagged (" + n(D.dupflag) + ")"],
    ["Missing Customer ID", "Retained as unidentified"]];
  const tbl = rows.map((rw, i) => rw.map((t, k) => ({ text: t, options: { bold: i === 0 || k === 0, color: i === 0 ? WHITE : TEXT, fill: { color: i === 0 ? NAVY : (i % 2 ? WHITE : LIGHT) }, fontFace: BF, fontSize: 11, valign: "middle" } })));
  s.addTable(tbl, { x: 5.1, y: 1.35, w: 4.4, colW: [2.1, 2.3], rowH: 0.43, border: { type: "solid", pt: 0.5, color: "D5DEE3" }, margin: [0.02, 0.07, 0.02, 0.07], objectName: "Cleaning rules" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.25, y: 1.35, w: 1.65, h: 1.15, fill: { color: LIGHT }, line: { color: LIGHT }, rectRadius: 0.08 });
  s.addText([{ text: "Business logic", options: { bold: true, color: NAVY, breakLine: true } }, { text: "line revenue = qty x price", options: { breakLine: true } }, { text: "cancellation flag, line key", options: {} }],
    { x: 3.32, y: 1.38, w: 1.55, h: 1.1, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  footer(s, "Source: reports/latest/cleaning_summary.json (run-001); configs/pipeline.yaml; cancellation lines = fact rows flagged is_cancellation");
  s.addNotes("The rules were set after profiling. Precedence is first-match, so retained + quarantined + excluded equals the raw row count exactly (1,067,371 = 1,033,062 + 5,973 + 28,336). Quarantine rows keep a reason code for review. Legitimate returns are not rejected: negative quantity is valid on a cancellation ('C') invoice. Exact duplicates inside one source block could be genuine repeated scans, so they are kept and flagged (11,790 rows) rather than deleted; a configuration switch can drop them. Missing Customer ID is not an error; those sales stay in revenue and product analytics but cannot feed customer-level models. Customer ID is replaced by a keyed pseudonym in this stage (slide 11). The 17,974 figure is the count of retained cancellation lines with negative quantity.");
}

// ---------------------------------------------------------------------------------------------------------- 7 Integration / outputs / lineage
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Integration, outputs and lineage", "One cleaned source organised into documented keys and grains");
  const T = D.tables;
  const rows = [["Output table", "Grain / key", "Rows", "Consumer"],
    ["fact_sales_line", "Invoice line / line_id", n(T.fact_sales_line), "Analytics layer"],
    ["dim_product", "Stock code", n(T.dim_product), "Inventory, forecasting"],
    ["dim_customer", "Pseudonymised customer", n(T.dim_customer), "Marketing, churn"],
    ["dim_date", "Calendar day", n(T.dim_date), "All reporting"],
    ["agg_daily_sales", "Day x country", n(T.agg_daily_sales), "Finance, Operations"],
    ["agg_weekly_sku_demand", "ISO week x stock code", n(T.agg_weekly_sku_demand), "Inventory and Procurement"],
    ["agg_customer_rfm_base", "Pseudonymised customer", n(T.agg_customer_rfm_base), "Marketing (RFM)"]];
  const tbl = rows.map((rw, i) => rw.map((t, k) => ({ text: t, options: { bold: i === 0 || k === 0, color: i === 0 ? WHITE : TEXT, fill: { color: i === 0 ? NAVY : (i % 2 ? WHITE : LIGHT) }, fontFace: BF, fontSize: 11, valign: "middle", align: k === 2 ? "right" : "left" } })));
  s.addTable(tbl, { x: 0.5, y: 1.3, w: 9, colW: [2.3, 2.5, 1.2, 3.0], rowH: 0.31, border: { type: "solid", pt: 0.5, color: "D5DEE3" }, margin: [0.02, 0.08, 0.02, 0.08], objectName: "Output tables" });
  const L = [["Quantity x Price", "line_revenue", "net and gross revenue"], ["Customer ID", "customer_key (HMAC)", "customer dim + RFM"], ["Invoice 'C' prefix", "is_cancellation", "cancellation metrics"]];
  L.forEach((l, i) => {
    const x = 0.5 + i * 3.05, y = 4.45;
    s.addText("Lineage " + (i + 1), { x, y: y - 0.27, w: 1.5, h: 0.22, fontFace: BF, fontSize: 11, bold: true, color: MUTED, margin: 0, isTextBox: true });
    box(s, x, y, 0.85, 0.62, l[0], SLATE, WHITE, { fs: 10 });
    arrow(s, x + 0.85, y + 0.31, x + 0.95, y + 0.31, SLATE);
    box(s, x + 0.95, y, 1.0, 0.62, l[1], NAVY, WHITE, { fs: 10 });
    arrow(s, x + 1.95, y + 0.31, x + 2.05, y + 0.31, SLATE);
    box(s, x + 2.05, y, 0.9, 0.62, l[2], TEAL, WHITE, { fs: 10 });
  });
  footer(s, "Source: docs/lineage.md, docs/data_dictionary.yaml, src/retail_pipeline/catalog.py (run-002 manifest row counts)");
  s.addNotes("Only one source exists, so no additional sources were invented. Integration here means conforming the cleaned transaction stream into a star-style model: one fact table, three dimensions and three aggregates, each with a documented primary key and grain. Published tables are consumed by the stakeholder groups from slide 2. The weekly SKU table is sparse: weeks without transactions are absent, so the forecasting stage must zero-fill. Full raw-to-output field lineage for every column is in docs/lineage.md, generated from the Data Dictionary.");
}

// ---------------------------------------------------------------------------------------------------------- 8 Orchestration
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Orchestration and reproducibility", "One command, deterministic outputs, failures stop publication");
  const cards = [
    ["Prefect DAG", "11 tasks; dependencies via futures; profile, bias and privacy run as branches", TEAL, "Executed"],
    ["Retries and failure", "ingest retries 2x; gates never retry; failed run writes FAILED status and publishes nothing", TEAL, "Executed"],
    ["Deterministic", D.repro.n + " of " + D.repro.n + " tables identical across two runs; build id " + D.build_id.slice(0, 8), TEAL, "Executed"],
    ["Pinned environment", "Lock file; fresh venv install + full test run; run in " + Math.round(D.runtime) + " s", TEAL, "Executed"],
    ["Docker image", "Dockerfile with unprivileged user and lock-file install", AMBER, "Not verified"],
    ["Collaboration", "Config-as-code, tests, CI template, generated docs", AMBER, "CI not run"],
  ];
  cards.forEach((c, i) => {
    const x = 0.5 + (i % 3) * 3.05, y = 1.35 + Math.floor(i / 3) * 1.55;
    card(s, x, y, 2.9, 1.4, LIGHT, "Control card");
    s.addShape(pres.shapes.OVAL, { x: x + 0.12, y: y + 0.12, w: 0.36, h: 0.36, fill: { color: c[2] }, line: { color: c[2] } });
    s.addText(String(i + 1), { x: x + 0.12, y: y + 0.12, w: 0.36, h: 0.36, fontFace: BF, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(c[0], { x: x + 0.58, y: y + 0.1, w: 2.2, h: 0.4, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, valign: "middle", isTextBox: true });
    s.addText(c[1], { x: x + 0.12, y: y + 0.55, w: 2.68, h: 0.82, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "top", isTextBox: true });
    tag(s, x + 1.65, y + 1.08, 1.15, c[3], c[2]);
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.5, w: 9, h: 0.6, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.08, objectName: "Command bar" });
  s.addText("python -m retail_pipeline.flow --run-id run-001", { x: 0.7, y: 4.5, w: 8.6, h: 0.6, fontFace: "Courier New", fontSize: 14, color: WHITE, margin: 0, valign: "middle", isTextBox: true });
  footer(s, "Source: reports/evidence/reproducibility_check.json, fresh_venv_check.txt; src/retail_pipeline/flow.py");
  s.addNotes("Two full runs with the same input, configuration, code and key produced identical content hashes for all seven published tables, and the same build id. The build id changes if the code or rules change, which was observed during development. Failure handling is demonstrated: a critical bronze failure in the integration test stops the run at the cleaning step, writes run_status.json as FAILED and publishes nothing. The pinned dependency set was installed in a fresh virtual environment and the full test suite ran there. Docker: the Dockerfile and commands are provided, but no Docker daemon was available where this was built, so the image has not been built or run. The CI workflow is a template that has not been executed.");
}

// ---------------------------------------------------------------------------------------------------------- 9 Validation
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Data validation", "Great Expectations gates: critical failures block publication");
  stat(s, 0.5, 1.3, 1.45, 0.95, D.val.bronze.expectations_passed + "/" + D.val.bronze.expectations_evaluated, "bronze checks", GREEN);
  stat(s, 2.05, 1.3, 1.45, 0.95, D.val.outputs.expectations_passed + "/" + D.val.outputs.expectations_evaluated, "output checks", GREEN);
  stat(s, 3.6, 1.3, 1.45, 0.95, D.val.reconciliation_passed + "/" + D.val.reconciliation_checks, "reconciliations", GREEN);
  s.addChart(pres.charts.BAR, [{ name: "Critical failures", labels: ["Real data run", "Injected-fault fixture"], values: [D.gate.baseline_critical_failures, D.gate.faulty_critical_failures] }],
    { x: 0.4, y: 2.35, w: 4.7, h: 2.85, barDir: "col", chartColors: [GREEN, CORAL], showValue: true, dataLabelPosition: "outEnd", valAxisHidden: true, valAxisMaxVal: 9, valAxisMinVal: 0, barGapWidthPct: 60, ...chartBase("Critical failures per validation run") });
  const rc = D.reasons, rr = D.reason_rev;
  const q = (rr.QRN_STOCK_ADJUSTMENT || 0) + (rr.QRN_ZERO_PRICE || 0), ex = (rr.EXC_DUP_OVERLAP || 0) + (rr.EXC_NON_MERCHANDISE || 0), ok = rr.OK;
  const money = (v) => "£" + n(Math.round(v));
  const lines = [
    ["Rows", n(D.disp.rows_raw) + " = " + n(D.disp.rows_retained) + " + " + n(D.disp.rows_quarantined) + " + " + n(D.disp.rows_excluded)],
    ["Revenue", money(D.recon[5].expected) + " = " + money(ok) + " + " + money(q) + " + " + money(ex)],
    ["Fact = daily = weekly", "net " + money(D.fact_revenue.actual) + "; differences 0.00"],
    ["Fixture", "dup key, negative price, raw-looking key, +1,000 revenue: 7 critical failures, publish blocked, no folder, LATEST unchanged"],
    ["Returns", n(17974) + " cancellation lines pass (negative qty is valid)"],
  ];
  card(s, 5.3, 1.3, 4.2, 3.9, LIGHT, "Reconciliation card");
  s.addText("Reconciliation (all within tolerance)", { x: 5.45, y: 1.38, w: 3.9, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText(lines.map((l, k) => [{ text: l[0] + ": ", options: { bold: true, color: TEAL } }, { text: l[1], options: { color: TEXT, breakLine: k < lines.length - 1 } }]).flat(),
    { x: 5.45, y: 1.75, w: 3.9, h: 3.35, fontFace: BF, fontSize: 12, margin: 0, valign: "top", paraSpaceAfter: 6, isTextBox: true });
  footer(s, "Source: reports/latest/validation_*.json, reconciliation.csv; reports/evidence/gate_failure_demo.json. GE 1.24.1; 0 warnings");
  s.addNotes("Validation uses Great Expectations 1.24.1 with severity levels. Critical failures block publication; warnings are recorded only. The real run passed all 16 bronze and 99 output expectations plus 13 reconciliation checks, with no warnings. To show the gate works, a controlled fixture took the real staged tables and injected four faults (duplicate primary key, negative retained price, a raw-looking customer key, and a +1,000 revenue change); the suite reported 7 critical failures, the publish function raised PublicationBlocked, no published folder was created and the LATEST pointer was unchanged. Rules were written so legitimate returns pass: a sign check only requires negative quantity to match a cancellation invoice. Amounts are in the dataset's currency, GBP per the dataset documentation.");
}

// ---------------------------------------------------------------------------------------------------------- 10 Bias
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Bias detection", "Internal representation imbalance, not proof of population bias");
  const top = D.bias.top;
  s.addChart(pres.charts.BAR, [{ name: "Share of lines", labels: top.map((t) => t[0]), values: top.map((t) => +(t[1] * 100).toFixed(2)) }],
    { x: 0.4, y: 1.25, w: 4.6, h: 2.45, barDir: "col", chartColors: [AMBER, TEAL, TEAL, TEAL, TEAL, TEAL], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', valAxisHidden: true, valAxisMaxVal: 110, barGapWidthPct: 40, catAxisLabelFontSize: 10, ...chartBase("Share of retained lines by country (top 6 of 43)") });
  const cf = D.bias.canc_flag.map((c) => [c[0], +(c[1] * 100).toFixed(1)]).concat([["Overall", +(D.bias.canc * 100).toFixed(1)]]).sort((a, b) => b[1] - a[1]);
  s.addChart(pres.charts.BAR, [{ name: "Cancellation rate", labels: cf.map((c) => c[0]), values: cf.map((c) => c[1]) }],
    { x: 5.0, y: 1.25, w: 4.6, h: 2.45, barDir: "col", chartColors: cf.map((c) => (c[0] === "Overall" ? SLATE : CORAL)), showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', valAxisHidden: true, valAxisMaxVal: 34, barGapWidthPct: 40, catAxisLabelFontSize: 10, ...chartBase("Flagged cancellation rates (invoices)") });
  const calls = [
    [D.bias.top[0][0] === "United Kingdom" ? pct(D.bias.top1, 0) : "", "of lines from one country; effective countries " + D.bias.eff, AMBER],
    [pct(D.bias.id_line, 0), "of lines have a Customer ID; " + pct(D.bias.unid_rev, 1) + " of revenue is unidentified", CORAL],
    [pct(D.bias.rm.unidentified, 1) + " vs " + pct(D.bias.rm.identified, 1), "cleaning removal: unidentified vs identified lines", TEAL],
    [pct(D.bias.q4, 0), "of revenue in Oct-Dec; Dec 2011 partial", NAVY],
  ];
  calls.forEach((c, i) => {
    const x = 0.5 + i * 2.28;
    card(s, x, 3.8, 2.1, 1.0, LIGHT, "Finding card");
    s.addText(c[0], { x: x + 0.08, y: 3.83, w: 1.95, h: 0.4, fontFace: HF, fontSize: 18, bold: true, color: c[2], margin: 0, valign: "middle", isTextBox: true });
    s.addText(c[1], { x: x + 0.08, y: 4.23, w: 1.95, h: 0.55, fontFace: BF, fontSize: 10, color: TEXT, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Mitigation: report group sizes, group small countries, keep unidentified sales in revenue analytics, flag partial months. No demographic fields exist; none inferred.", { x: 0.5, y: 4.85, w: 9, h: 0.38, fontFace: BF, fontSize: 11, italic: true, color: MUTED, margin: 0, valign: "top", isTextBox: true });
  footer(s, "Source: reports/latest/bias_report.json (run-001). Screening band 0.8-1.25, min 100 invoices, 95% Wilson CI; no external benchmark");
  s.addNotes("The bias suite measures representation using the only group attribute available, Country, plus time coverage, customer-identification coverage and cancellation patterns. There is no external benchmark, so reference points are the dataset's own overall rates and equal calendar coverage; findings are labelled internal representation imbalance. The United Kingdom holds 92% of lines (85.6% of gross sales revenue), 39 of 43 countries each hold under 1% of lines and 20 have fewer than 5 identified customers, so non-UK conclusions rest on thin samples. Cancellation rates are flagged for Germany, Switzerland and EIRE (high) and the Netherlands (low) when the ratio to the overall 15.8% is outside 0.8-1.25 with at least 100 invoices and a confidence interval that excludes the overall rate. Cleaning removes a larger share of unidentified-customer lines (6.5% vs 2.3%); the cause was not analysed here. Implications: UK-dominated KPIs, customer models limited to identified customers, seasonality estimated from about two cycles. Limitations: ratio bands are screening heuristics, not legal tests; demographic fairness cannot be assessed.");
}

// ---------------------------------------------------------------------------------------------------------- 11 Privacy and governance
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Privacy and governance", "Pseudonymous, not anonymous: controls built on the Module 2 Privacy Plan");
  const rows = [["Class", "In the data", "Treatment"],
    ["Direct identifiers", "None found; " + D.staff + " staff first names in descriptions", "Redacted on ingestion"],
    ["Pseudonymous", "Customer ID (22.8% missing)", "Keyed HMAC-SHA256; secret from env var"],
    ["Quasi-identifiers", "Country, timestamp, basket", D.bias.small + " countries under 5 customers flagged"],
    ["Sensitive / protected", "None present; none inferred", "Fairness limited to country"]];
  const tbl = rows.map((rw, i) => rw.map((t, k) => ({ text: t, options: { bold: i === 0 || k === 0, color: i === 0 ? WHITE : TEXT, fill: { color: i === 0 ? NAVY : (i % 2 ? WHITE : LIGHT) }, fontFace: BF, fontSize: 11, valign: "middle" } })));
  s.addTable(tbl, { x: 0.5, y: 1.3, w: 5.3, colW: [1.35, 2.0, 1.95], rowH: [0.34, 0.62, 0.62, 0.62, 0.55], border: { type: "solid", pt: 0.5, color: "D5DEE3" }, margin: [0.02, 0.07, 0.02, 0.07], objectName: "Identifier inventory" });
  card(s, 0.5, 4.2, 5.3, 0.9, "FFF3DC", "Accuracy note");
  s.addText("Pseudonymised data stays personal data: whoever holds the secret or raw IDs can re-link. Published S2 tables need restricted access.", { x: 0.62, y: 4.22, w: 5.1, h: 0.86, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  card(s, 6.0, 1.3, 3.5, 1.9, LIGHT, "Access card");
  s.addText("Access and retention", { x: 6.12, y: 1.36, w: 2.3, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: NAVY, margin: 0, isTextBox: true });
  tag(s, 8.4, 1.38, 1.0, "PROPOSED", AMBER);
  s.addText([
    { text: "Pipeline service: raw, bronze", options: { bullet: true, breakLine: true } },
    { text: "Stewards: silver; Marketing: S2 tables", options: { bullet: true, breakLine: true } },
    { text: "Aggregates: all stakeholders", options: { bullet: true, breakLine: true } },
    { text: "Retention: silver 30 d, published 730 d", options: { bullet: true } },
  ], { x: 6.12, y: 1.72, w: 3.3, h: 1.45, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "top", paraSpaceAfter: 3, isTextBox: true });
  card(s, 6.0, 3.3, 3.5, 1.8, "DCEFEF", "Audit card");
  s.addText("Privacy audit log", { x: 6.12, y: 3.36, w: 2.3, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: NAVY, margin: 0, isTextBox: true });
  tag(s, 8.1, 3.38, 1.3, "IMPLEMENTED", GREEN);
  s.addText([
    { text: D.audit.events + " events: run id, time, actor, operation, dataset, rows, outcome", options: { bullet: true, breakLine: true } },
    { text: "0 customer keys or secrets found in the log", options: { bullet: true, breakLine: true } },
    { text: "Covers pipeline access only; platform logs needed elsewhere", options: { bullet: true } },
  ], { x: 6.12, y: 3.72, w: 3.3, h: 1.35, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "top", paraSpaceAfter: 3, isTextBox: true });
  footer(s, "Source: reports/latest/privacy_report.json, audit_events.jsonl; docs/governance.md; Module 2 Privacy Plan s6.1. Roles/retention are proposals");
  s.addNotes("Identifier inventory from the actual fields: no direct identifiers were found; Customer ID is a pseudonymous identifier and is replaced by an HMAC-SHA256 keyed pseudonym before any table leaves the restricted bronze zone. The secret comes from the CUSTOMER_KEY_SECRET environment variable and is never written to Git, logs or reports; Key Vault is the recommended production home. Staff first names appeared in " + D.staff + " ledger-style descriptions and are redacted. Roles, access zones and retention periods are proposed policies pending the DPO and data owner; they are not enforced by the code, and the retention value is a placeholder. The audit log records metadata for every pipeline-managed read, write, transformation, validation and publication; it cannot see reads by people or other tools, which need storage-platform audit controls. Incident handling and data-subject deletion procedures are documented as proposals only.");
}

// ---------------------------------------------------------------------------------------------------------- 12 Evidence and repo
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  header(s, "Execution evidence and repository", "What was run and verified, and what was not");
  const ev = [
    ["Pipeline run", "2 runs SUCCEEDED, " + Math.round(D.runtime) + " s each, " + n(D.rows) + " rows", GREEN],
    ["Validation", "115 expectations + 13 reconciliations passed", GREEN],
    ["Tests", D.tests + " passed in a fresh pinned venv", GREEN],
    ["Failing fixture", "7 critical failures; publication blocked", GREEN],
    ["Reproducibility", D.repro.n + "/" + D.repro.n + " tables identical", GREEN],
    ["Docker build, CI, GitHub push", "Not verified / not done", CORAL],
  ];
  ev.forEach((e, i) => {
    const y = 1.3 + i * 0.6;
    card(s, 0.5, y, 5.1, 0.52, LIGHT, "Evidence row");
    s.addShape(pres.shapes.OVAL, { x: 0.62, y: y + 0.13, w: 0.26, h: 0.26, fill: { color: e[2] }, line: { color: e[2] } });
    s.addText(e[2] === GREEN ? "✓" : "!", { x: 0.62, y: y + 0.13, w: 0.26, h: 0.26, fontFace: BF, fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(e[0], { x: 1.0, y, w: 1.75, h: 0.52, fontFace: BF, fontSize: 12, bold: true, color: NAVY, margin: 0, valign: "middle", isTextBox: true });
    s.addText(e[1], { x: 2.75, y, w: 2.8, h: 0.52, fontFace: BF, fontSize: 11, color: TEXT, margin: 0, valign: "middle", isTextBox: true });
  });
  card(s, 5.8, 1.3, 3.7, 1.25, NAVY, "Repository card");
  s.addText("GitHub repository", { x: 5.95, y: 1.36, w: 3.4, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: AMBER, margin: 0, isTextBox: true });
  s.addText([{ text: "Open repository on GitHub (DrChitsungo)", options: { hyperlink: { url: "https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-", tooltip: "Open the project repository on GitHub" }, color: "8FD6D6", underline: { style: "sng", color: "8FD6D6" }, breakLine: true } }, { text: "Link supplied by the author. This build did not push to it; contents not verified here.", options: { color: WHITE, fontSize: 10 } }], { x: 5.95, y: 1.7, w: 3.4, h: 0.8, fontFace: BF, fontSize: 11, margin: 0, valign: "top", isTextBox: true, objectName: "Repository link" });
  s.addText("Remaining limitations", { x: 5.8, y: 2.7, w: 3.7, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText([
    { text: "One static source; no cost or ERP/CRM data", options: { bullet: true, breakLine: true } },
    { text: "Bias is internal; no benchmark or demographics", options: { bullet: true, breakLine: true } },
    { text: "Roles, retention, DPIA: proposals", options: { bullet: true, breakLine: true } },
    { text: "Source block boundary is inferred", options: { bullet: true } },
  ], { x: 5.8, y: 3.05, w: 3.7, h: 1.6, fontFace: BF, fontSize: 12, color: TEXT, margin: 0, valign: "top", paraSpaceAfter: 4, isTextBox: true });
  footer(s, "Evidence: reports/evidence/ (pytest_results.txt, gate_failure_demo.json, reproducibility_check.json, fresh_venv_check.txt)");
  s.addNotes("Everything marked as passed was executed and its output is stored in the repository's reports folder. Two things were not possible in this environment: the Docker image could not be built because no Docker daemon was available, and nothing was committed or pushed to GitHub. The repository link on this slide is the one you supplied and is clickable. This session did not push to it, so confirm it contains the package (including Dockerfile and reports) before submission. The CI workflow file is a template that has not run. Remaining limitations are summarised on the slide; see README section 9.");
}

(async () => {
  const out = path.join(__dirname, "Module3_Retail_Pipeline.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
