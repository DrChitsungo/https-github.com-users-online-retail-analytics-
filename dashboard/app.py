"""Module 5 stakeholder dashboard: 90-day customer churn model (Module 4, v1.0.0). Run: streamlit run dashboard/app.py
Audience: Marketing and CRM managers. Historical results come from stored Module 4 evidence (aggregates only); new predictions come from the live Module 4 API."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd, plotly.graph_objects as go, streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dash_lib.core import ApiClient, LABELS, MIN_N, apply_scenario, fmt_pct, load_evidence, metrics_from_counts, to_payload

TEAL, AMBER, SLATE, RED, GREY = "#1C7C7D", "#F2A541", "#33415C", "#B23A48", "#8A93A3"
REPO = "https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-"
st.set_page_config(page_title="Customer churn model: stakeholder dashboard", page_icon=":bar_chart:", layout="wide")

@st.cache_data
def ev(): return load_evidence()
E = ev(); M = E["meta"]; H = E["headline"]; F = E["fairness"]; THR = M["threshold"]
api = ApiClient()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("Churn model dashboard")
view = st.sidebar.radio("View", ["Business overview", "Results and explanations", "Prediction and what-if", "Fairness and ethics", "About and evidence"])
st.sidebar.markdown("**Filters** (apply to the figures labelled *filtered*)")
month = st.sidebar.selectbox("Prediction month (held-out test)", ["All", "2011-08", "2011-09"])
group = st.sidebar.selectbox("Customer group", ["All", "UK", "Non-UK"], help="UK vs non-UK is an operational grouping, not a protected attribute.")
cell = E["filter_grid"][f"{month}|{group}"]; FM = metrics_from_counts(cell)
st.sidebar.caption(f"Model v{M['model_version']} | threshold {THR:.3f} | {FM['n']:,} customer-snapshots selected")
if FM["small_sample"]:
    st.sidebar.warning(f"Fewer than {MIN_N} customer-snapshots: treat these figures as unreliable.")

def banner(kind):
    if kind == "hist":
        st.info("**Historical evaluation** on the held-out test period (Aug-Sep 2011). These are stored results, not new predictions.")
    elif kind == "static":
        st.caption("Static: computed once on all test rows. Filters do not change this figure.")

def tile(col, label, value, note=""):
    col.metric(label, value); col.caption(note)

def chart(fig, h=340):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), font=dict(size=13), plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ 1. overview
if view == "Business overview":
    st.title("Which established customers may stop buying in the next 90 days?")
    st.markdown(f"""**Purpose.** Support Marketing and CRM managers who plan retention campaigns. For each identified customer with at least 180 days of purchase history the model gives a **risk score** for placing **no sales invoice in the 90 days after the prediction date**.
It is advisory and needs human review. It does not make decisions about individuals.""")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Data coverage**  \nProject: Online Retail II (UK giftware retailer)  \nTest period: {M['test_window']}  \n{M['test_rows']:,} customer-snapshots, {M['test_customers']:,} customers")
    c2.markdown(f"**Model**  \nLogistic regression v{M['model_version']}  \n18 behavioural features  \nFlag threshold {THR:.3f} (chosen on validation data)")
    c3.markdown("**Status**  \nPilot-stage prototype. The 90-day churn window and the 180-day history rule were agreed with the Marketing Director on 1 November 2026.")
    banner("hist")
    st.subheader(f"Selected group: {month} / {group}  (filtered)")
    a, b, c, d, e = st.columns(5)
    tile(a, "Customer-snapshots", f"{FM['n']:,}", "One customer on one prediction date")
    tile(b, "Actually lapsed", fmt_pct(FM["prevalence"]), "Share with no invoice in the next 90 days")
    tile(c, "Flagged by model", fmt_pct(FM["flag_rate"]), "Share the model marks as higher risk")
    tile(d, "Lapsers caught (recall)", fmt_pct(FM["recall"]), "Of customers who lapsed, the share flagged")
    tile(e, "Flags that were right", fmt_pct(FM["precision"]), "Of flagged customers, the share who lapsed")
    if cell["tp"] + cell["fn"] == 0 or cell["tp"] + cell["fp"] == 0:
        st.warning("Recall or precision is undefined for this selection because a denominator is zero.")
    st.subheader("What the verified results say")
    L = H["logreg"]; B = H["baseline_recency_rule"]; ci = H["logreg_ci"]; AS = E["active_subset"]
    st.markdown(f"""
- **Ranking ability is better than a simple rule.** ROC-AUC (ability to rank lapsers above stayers; 0.5 is chance) is **{L['roc_auc']:.3f}** (95% interval {ci['roc_auc'][0]:.3f}-{ci['roc_auc'][1]:.3f}) against **{B['roc_auc']:.3f}** for a "longest-silent customers first" rule. *Static, all test rows.*
- **The default threshold casts a wide net.** It flags **{fmt_pct(L['flag_rate'])}** of customers and catches **{fmt_pct(L['recall'])}** of lapsers, but only **{fmt_pct(L['precision'])}** of flags are correct (flagging everyone would be right {fmt_pct(L['prevalence'])} of the time). *Static.*
- **Two kinds of error have different costs.** On the test period **{L['fp']:,}** customers were flagged but kept buying (possible wasted offers) and **{L['fn']:,}** lapsers were missed. *Static.*
- **A shorter list is possible.** Flagging the top 20% by score gives {fmt_pct(E['operating_points'][0]['precision'])} precision and {fmt_pct(E['operating_points'][0]['recall'])} recall. See *Results and explanations*. *Static.*
- **Much of the result comes from long-silent customers.** {fmt_pct(AS['no_purchase_in_prior_180_days']['n'] / AS['all_eligible']['n'])} of the test customer-snapshots had no purchase in the 180 days before the prediction date; {fmt_pct(AS['no_purchase_in_prior_180_days']['prevalence'])} of them lapsed and the model flags {fmt_pct(AS['no_purchase_in_prior_180_days']['flag_rate'])} of them. Among customers who also bought in the prior 180 days, ROC-AUC is {AS['also_bought_in_prior_180_days']['roc_auc']:.3f} and only {fmt_pct(AS['also_bought_in_prior_180_days']['precision'])} of flags are correct. *Static.*
- **Scores are for ranking.** They are not recalibrated probabilities: the average score is {M['mean_score']:.2f} against an actual lapse rate of {M['prevalence']:.2f}.
""")
    st.caption("Filtered figures are recomputed from stored confusion-matrix counts at the fixed threshold. Static figures are labelled as such.")

# ------------------------------------------------------------------ 2. results
elif view == "Results and explanations":
    st.title("Results and explanations")
    banner("hist")
    t1, t2, t3, t4 = st.tabs(["How well does it work?", "Where it errs", "What drives scores", "Individual examples"])
    with t1:
        names = ["Flag everyone (no skill)", "Recency rule", "Logistic regression (chosen)", "LightGBM", "Random forest"]
        vals = [H["baseline_prevalence"]["roc_auc"], H["baseline_recency_rule"]["roc_auc"], H["logreg"]["roc_auc"], H["lightgbm_auc"], H["random_forest_auc"]]
        fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=[GREY, GREY, TEAL, AMBER, AMBER], text=[f"{v:.3f}" for v in vals], textposition="outside"))
        fig.update_layout(title="ROC-AUC on the test period (higher ranks lapsers better; 0.5 = chance)", xaxis=dict(range=[0, 1]))
        chart(fig, 300); banner("static")
        st.markdown("The chosen model ranks customers clearly better than the rule. LightGBM and random forest scored about the same (statistically indistinguishable; the random forest was slightly higher), so the simpler, more explainable model was chosen by a rule fixed in advance.")
        st.subheader("Choosing how many customers to contact")
        op = pd.DataFrame(E["operating_points"]); op["flag_rate"] = (op.flag_rate * 100).round(0).astype(int).astype(str) + "%"
        fig = go.Figure()
        x = [int(s.rstrip('%')) for s in op.flag_rate]
        fig.add_trace(go.Scatter(x=x, y=op.precision, name="Precision (flags that are right)", line=dict(color=TEAL, width=3)))
        fig.add_trace(go.Scatter(x=x, y=op.recall, name="Recall (lapsers caught)", line=dict(color=AMBER, width=3)))
        fig.update_layout(title="Trade-off by share of customers flagged", xaxis_title="Share of customers flagged (%)", yaxis=dict(tickformat=".0%", range=[0, 1]))
        chart(fig, 320); banner("static")
        st.caption(f"Flagging fewer customers raises precision and lowers recall. The fixed threshold {THR:.3f} flags {fmt_pct(H['logreg']['flag_rate'])}.")
        st.subheader("Are scores like probabilities?")
        cal = pd.DataFrame(E["calibration_deciles"])
        fig = go.Figure(); fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GREY, dash="dash"), name="Perfect calibration"))
        fig.add_trace(go.Scatter(x=cal.mean_score, y=cal.observed_churn, mode="lines+markers", marker=dict(size=9), line=dict(color=TEAL), name="Test deciles"))
        fig.update_layout(title="Average score vs actual lapse rate, by score decile", xaxis_title="Average score", yaxis_title="Actual lapse rate")
        chart(fig, 330); banner("static")
        st.markdown(f"Across all customers the average score ({M['mean_score']:.3f}) is a little below the actual lapse rate ({M['prevalence']:.3f}), and the model was **not recalibrated** (the lapse rate also differs between periods). Use scores to **rank** customers, not as guaranteed frequencies.")
    with t2:
        st.subheader(f"Confusion matrix, selected group: {month} / {group}  (filtered)")
        z = [[cell["tn"], cell["fp"]], [cell["fn"], cell["tp"]]]
        fig = go.Figure(go.Heatmap(z=z, x=["Not flagged", "Flagged"], y=["Kept buying", "Lapsed"], text=[[f"{v:,}" for v in r] for r in z], texttemplate="%{text}", colorscale=[[0, "#EAF4F4"], [1, TEAL]], showscale=False))
        fig.update_layout(xaxis_title="Model output", yaxis_title="What actually happened", yaxis_autorange="reversed")
        chart(fig, 320)
        st.markdown(f"""- **Flagged and lapsed (right flags):** {cell['tp']:,}
- **Flagged but kept buying (false alarms):** {cell['fp']:,}. Possible cost: unnecessary offers or contact.
- **Not flagged but lapsed (missed):** {cell['fn']:,}. Possible cost: lost chance to intervene.
- **Not flagged and kept buying:** {cell['tn']:,}""")
        auc = f"{FM['auc']:.3f}" if FM["auc"] is not None else "undefined"
        st.caption(f"ROC-AUC for this exact selection: {auc} (precomputed for each filter combination). {'Small sample: interpret with caution.' if FM['small_sample'] else ''}")
        st.subheader("Score distribution (static)")
        h = E["score_histogram"]; mids = [(h["bin_edges"][i] + h["bin_edges"][i + 1]) / 2 for i in range(len(h["churned"]))]
        fig = go.Figure(); fig.add_bar(x=mids, y=h["retained"], name="Kept buying", marker_color=GREY); fig.add_bar(x=mids, y=h["churned"], name="Lapsed", marker_color=AMBER)
        fig.add_vline(x=THR, line_dash="dash", line_color=SLATE, annotation_text=f"threshold {THR:.3f}"); fig.update_layout(barmode="overlay", title="Customer-snapshots by score", xaxis_title="Risk score", yaxis_title="Customer-snapshots")
        fig.update_traces(opacity=0.75); chart(fig, 320); banner("static")
        st.markdown("The two groups overlap heavily. That overlap is why the model makes errors in both directions.")
    with t3:
        st.subheader("What moves the risk score most")
        gi = pd.Series(E["global_shap"]["group_importance"]).sort_values()
        fig = go.Figure(go.Bar(x=gi.values, y=gi.index, orientation="h", marker_color=TEAL)); fig.update_layout(title="Importance by behaviour group (average absolute SHAP, log-odds)", xaxis_title="Average influence on the score")
        chart(fig, 340); banner("static")
        d = E["global_shap"]["direction_spearman"]
        def dir_txt(feat, label):
            rho = d.get(feat)
            return None if rho is None else f"- **{label}**: higher values go with a **{'higher' if rho > 0 else 'lower'}** risk score."
        lines = [dir_txt("Invoices (all history)", "Invoices (all history)"), dir_txt("Days since first purchase", "Days since first purchase"), dir_txt("Invoices, last 90d", "Invoices, last 90 days"), dir_txt("Revenue (all history)", "Revenue (all history)")]
        st.markdown("\n".join(l for l in lines if l))
        st.markdown("""**How to read this.** Customers who buy more often, and who bought recently, tend to score lower. These are **associations the model learned, not causes**: buying more invoices does not by itself make a customer stay. Related features can offset one another (for example, longer tenure raises the score when the number of invoices is held equal, because fewer purchases per month means less engagement), so individual directions should be read together.
SHAP measures how much each factor pushes one prediction up or down from the average; the chart averages that push across 2,000 test rows.""")
        ag = E["global_shap"]["agreement_with_lightgbm"]
        st.caption(f"Cross-check: a LightGBM model agrees on {ag['top5_overlap']} of its top 5 features (rank correlation {ag['spearman_rank_logreg_vs_lightgbm']:.2f}), so rankings of individual features are somewhat model-dependent.")
    with t4:
        st.markdown(f"**How these cases were chosen.** A fixed rule, not by hand: {E['case_rule'].replace(chr(10), ' ')} Two of the five are errors, shown on purpose.")
        key = st.selectbox("Choose a held-out example", list(E["cases"]), format_func=lambda k: E["cases"][k]["label"])
        cs = E["cases"][key]
        a, b, c = st.columns(3)
        tile(a, "Stored risk score", f"{cs['stored_score']:.2f}", f"Threshold {THR:.3f}"); tile(b, "Model flagged?", "Yes" if cs["flagged"] else "No"); tile(c, "What actually happened", "Lapsed" if cs["actual_churn"] else "Kept buying")
        dr = pd.DataFrame(cs["top_drivers"]).iloc[::-1]
        fig = go.Figure(go.Bar(x=dr.shap_log_odds, y=dr.feature, orientation="h", marker_color=[RED if v > 0 else TEAL for v in dr.shap_log_odds], text=[f"value {v:g}" for v in dr.value], textposition="auto"))
        fig.update_layout(title="Main factors (right = raises risk score, left = lowers it)", xaxis_title="Push on the score (log-odds)"); chart(fig, 300)
        notes = {"A_typical_true_positive": "A typical correct flag: only two invoices in 372 days, the latest 330 days before the prediction date, so no recent purchases raised the score, and the customer did lapse.",
                 "B_typical_true_negative": "A typical correct 'no flag': nine invoices and a purchase four days earlier kept the score low, and the customer kept buying.",
                 "C_confident_false_positive": "A confident false alarm. This customer made one small purchase 512 days before the prediction date and nothing since, which looks like a lapsed customer, but they bought again. History alone cannot see a customer returning for seasonal or other reasons.",
                 "D_missed_churner_false_negative": "A missed churner: a frequent, high-value customer (31 invoices) who last bought 28 days earlier. Nothing in the history signalled a lapse, yet they stopped. The model cannot see outside events.",
                 "E_borderline": "A borderline case: 11 invoices over 632 days lower the score but no purchase in the last 90 days raises it, leaving the score close to the threshold. A small change in inputs would flip the flag."}
        st.info(notes[key]); st.caption("Example identifiers and dates are withheld. Explanations describe the model's prediction, not why the customer actually behaved as they did.")

# ------------------------------------------------------------------ 3. prediction / what-if
elif view == "Prediction and what-if":
    st.title("Prediction and what-if explorer")
    st.warning("**This page makes new predictions** by calling the Module 4 API. It is separate from the historical results elsewhere in the dashboard.")
    h = api.health(); mi = api.model() if h["ok"] else None
    if not h["ok"]:
        st.error(h.get("error") or f"The model API answered HTTP {h.get('status')}. Predictions are unavailable until it is reachable.")
        st.stop()
    st.success(f"Model API reachable: version {h['body']['model_version']}, decision threshold {mi['body']['threshold']:.6f} ({api.base})")
    keys = list(E["cases"]); base_key = st.selectbox("Start from a held-out example profile (values rounded for privacy)", keys, format_func=lambda k: E["cases"][k]["label"])
    base = E["cases"][base_key]["profile"]
    st.markdown("**Scenario.** Imagine the customer had made extra purchases at their own average order value. Everything not listed below (tenure, product breadth, gap statistics, cancellations, country) is held fixed, and dependent figures are recalculated.")
    c1, c2 = st.columns(2)
    k = c1.slider("Extra invoices", 0, 6, 3, help="Module 4's counterfactual search used up to six.")
    allowed = [r for r in (1, 7, 14, 30, 60, 90)]
    r = c2.selectbox("Days before the prediction date that the latest purchase happened", allowed, index=5)
    scen = apply_scenario(base, k, r)
    diff = pd.DataFrame([{"Feature": LABELS[f], "Original": base[f], "Scenario": round(scen[f], 2) if scen[f] is not None else None} for f in base if base[f] != scen[f]])
    st.markdown("**What changes in the scenario**" if len(diff) else "No fields change at 0 extra invoices.")
    if len(diff): st.dataframe(diff, hide_index=True, use_container_width=True)
    if st.button("Score both profiles with the live API", type="primary"):
        st.session_state["res"] = (base_key, k, r, api.predict(to_payload(base)), api.predict(to_payload(scen)))
    res = st.session_state.get("res")
    if res and res[:3] == (base_key, k, r):
        o, s = res[3], res[4]
        if not (o["ok"] and s["ok"]):
            st.error("The API rejected or could not score a profile.")
            for nm, x in (("Original", o), ("Scenario", s)): st.write(nm, x.get("error") or x.get("body"))
        else:
            ob, sb = o["body"], s["body"]
            a, b, c = st.columns(3)
            tile(a, "Original risk score (live API)", f"{ob['churn_probability']:.3f}", "FLAGGED" if ob["flagged_high_churn_risk"] else "not flagged")
            tile(b, "Scenario risk score (live API)", f"{sb['churn_probability']:.3f}", "FLAGGED" if sb["flagged_high_churn_risk"] else "not flagged")
            tile(c, "Change", f"{sb['churn_probability'] - ob['churn_probability']:+.3f}", f"threshold {ob['decision_threshold']:.3f}")
            st.caption(f"Model version {ob['model_version']} | request ids {ob['request_id'][:8]}..., {sb['request_id'][:8]}... | stored evaluation score for this example: {E['cases'][base_key]['stored_score']:.3f} (differs slightly because profile values are rounded for privacy)")
            if ob["imputed_fields"] or sb["imputed_fields"]: st.caption("Missing gap statistics were replaced with training medians by the API.")
            if bool(ob["flagged_high_churn_risk"]) != bool(E["cases"][base_key]["flagged"]):
                st.warning("The stored evaluation flag differs from the live flag for this example. Its score sits on the threshold, and rounding the profile for privacy moved it across. This shows how fragile a flag is near the boundary.")
    st.markdown("""**How to read this.** It shows how the **model's score** responds to a changed history. It is **not** a causal intervention: making a customer buy more would not necessarily change their score the same way, and a changed score does not guarantee a changed real-world outcome. Only behaviour that could realistically change was varied; no personal or protected characteristic was changed.""")
    with st.expander("Test how the API handles an invalid request"):
        st.caption("This sends an ineligible profile (tenure below the 180-day eligibility minimum) to the same API.")
        if st.button("Send invalid request"):
            bad = to_payload(base) | {"tenure_days": 5.0, "recency_days": 100.0}
            x = api.predict(bad); st.write(f"HTTP {x.get('status')}"); st.json(x.get("body") or {"error": x.get("error")})

# ------------------------------------------------------------------ 4. fairness
elif view == "Fairness and ethics":
    st.title("Fairness and ethical compliance view")
    st.error("**No protected attributes exist in this dataset**, and none were inferred. The figures below are an *operational* comparison of UK and non-UK customers. They do **not** show that the model is fair, and they are **not** a regulatory or legal compliance assessment.")
    banner("hist"); st.caption(f"Static: all fairness figures use all {M['test_rows']:,} test customer-snapshots at the fixed threshold and are not affected by the sidebar filters.")
    cmp_ = F["comparisons"]["Non-UK"]; tab = pd.DataFrame(F["table"]).set_index("group")
    st.subheader("Who was compared")
    st.markdown(f"**Reference group:** UK (n = {int(tab.loc['UK','n']):,}). **Comparison group:** non-UK (n = {int(tab.loc['Non-UK','n']):,}; wider uncertainty). A *favourable* outcome here is ambiguous: being flagged triggers retention outreach, which can be a benefit (an offer) or a burden (unwanted contact), so both flag rates and error rates matter.")
    rows = []
    for g in ("UK", "Non-UK"):
        t = tab.loc[g]; rows += [("Flag rate", g, t.selection_rate, t.sel_lo, t.sel_hi), ("Lapsers caught (TPR)", g, t.tpr, t.tpr_lo, t.tpr_hi), ("False-alarm rate (FPR)", g, t.fpr, t.fpr_lo, t.fpr_hi)]
    df = pd.DataFrame(rows, columns=["Metric", "Group", "v", "lo", "hi"]); fig = go.Figure()
    for g, colr in (("UK", TEAL), ("Non-UK", AMBER)):
        d = df[df.Group == g]; fig.add_bar(x=d.Metric, y=d.v, name=g, marker_color=colr, error_y=dict(type="data", symmetric=False, array=d.hi - d.v, arrayminus=d.v - d.lo))
    fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%", range=[0, 1]), title="Outcomes by group with 95% intervals"); chart(fig, 360)
    st.subheader("Measured disparities against the project's stated thresholds")
    chk = cmp_["checks"]
    out = pd.DataFrame([
        ["Disparate impact ratio (flag rate non-UK / UK)", f"{cmp_['disparate_impact_ratio']:.3f}  ({cmp_['ci_disparate_impact_ratio'][0]:.3f} to {cmp_['ci_disparate_impact_ratio'][1]:.3f})", "0.80 to 1.25", "Within" if chk["disparate_impact_in_0.8_1.25"] else "Outside"],
        ["Demographic parity difference (flag rate gap)", f"{cmp_['demographic_parity_difference']:+.3f}  ({cmp_['ci_demographic_parity_difference'][0]:+.3f} to {cmp_['ci_demographic_parity_difference'][1]:+.3f})", "interval spans 0 = no clear gap", "Interval includes 0"],
        ["Lapsers-caught gap (TPR difference)", f"{cmp_['tpr_difference']:+.3f}  ({cmp_['ci_tpr_difference'][0]:+.3f} to {cmp_['ci_tpr_difference'][1]:+.3f})", "TPR within 10% of overall", "Within" if chk["tpr_within_10pct_of_overall"] else "Outside"],
        ["False-alarm gap (FPR difference)", f"{cmp_['fpr_difference']:+.3f}  ({cmp_['ci_fpr_difference'][0]:+.3f} to {cmp_['ci_fpr_difference'][1]:+.3f})", "FPR within 10% of overall", "Within" if chk["fpr_within_10pct_of_overall"] else "Outside"],
    ], columns=["Measure", "Value (95% interval)", "Project threshold", "Status"])
    st.dataframe(out, hide_index=True, use_container_width=True)
    ok_fpr = chk["fpr_within_10pct_of_overall"]
    st.markdown(f"""**What this means.** The flag rates are similar (ratio {cmp_['disparate_impact_ratio']:.2f}) and lapsers are caught at similar rates. The false-alarm rate (customers who kept buying but were flagged) is {tab.loc['Non-UK','fpr']:.1%} for non-UK and {tab.loc['UK','fpr']:.1%} for UK customers; the ratio to overall is {cmp_['fpr_vs_overall']:.2f}, {'inside' if ok_fpr else 'outside'} the Module 1 band of 0.90 to 1.10. The interval for the gap ({cmp_['ci_fpr_difference'][0]:.3f} to {cmp_['ci_fpr_difference'][1]:.3f}) includes zero because only {int(tab.loc['Non-UK','n'])} snapshots are non-UK, so this is not evidence that the groups are treated the same. A higher non-UK false-alarm rate seen under the earlier eligibility rule was not reproduced under the rule agreed with Marketing, and it is not claimed to be eliminated.
The thresholds are governance bands set in Modules 1 and 2, not legal tests, so a result is described as *within* or *outside the project's stated threshold*.""")
    st.subheader("Mitigation that was actually performed")
    mt = pd.DataFrame([{"Approach": {"M0_unmitigated_selected_model": "None (selected model)", "M1_threshold_optimizer_equalized_odds": "Group-specific thresholds (Fairlearn ThresholdOptimizer)", "M2_reweighing_refit": "Reweighing and refit (Kamiran-Calders)"}.get(k, k),
                       "Validation recall": v["validation"]["recall"], "Test false-alarm gap (non-UK minus UK)": v["test_exploratory"]["fpr_NonUK"] - v["test_exploratory"]["fpr_UK"],
                       "Test recall": v["test_exploratory"]["recall"], "Test flag rate": v["test_exploratory"]["flag_rate"]} for k, v in F["mitigation"].items()])
    st.dataframe(mt.style.format({c: "{:.3f}" for c in mt.columns if c != "Approach"}), hide_index=True, use_container_width=True)
    gap = lambda k: F["mitigation"][k]["test_exploratory"]["fpr_NonUK"] - F["mitigation"][k]["test_exploratory"]["fpr_UK"]
    st.markdown(f"No governance band was breached on test, so neither mitigation was needed and **neither was adopted**. Group-specific thresholds lowered recall to {F['mitigation']['M1_threshold_optimizer_equalized_odds']['test_exploratory']['recall']:.3f} (from {F['mitigation']['M0_unmitigated_selected_model']['test_exploratory']['recall']:.3f}) and reweighing left the results essentially unchanged. Test-period mitigation numbers are exploratory. Removing the country flag from the model changed validation AUC by less than 0.0001, so country is not used as a predictor.")
    st.subheader("Sample sizes by country (minimum 100 for a reliable comparison)")
    pc = pd.DataFrame(F["per_country"]).sort_values("n", ascending=False)
    fig = go.Figure(go.Bar(x=pc.group, y=pc.n, marker_color=[TEAL if s else GREY for s in pc.sufficient_n], text=pc.n, textposition="outside")); fig.add_hline(y=F["min_group_n"], line_dash="dash", annotation_text="minimum 100"); fig.update_layout(yaxis_type="log", title="Customer-snapshots per country (log scale; grey = too few)"); chart(fig, 320)
    st.subheader("Customer-segment audit (behavioural, not protected)")
    SA = E["segment_audit"]
    st.caption("Tenure, spend and purchase-frequency tiers are behavioural segments, not demographic groups and not protected characteristics. Exploratory, descriptive, test period; the model and threshold were not changed. Tier cut-offs come from the training snapshots only.")
    srows = []
    for key, lab in (("tenure_tier", "Tenure"), ("spend_tier", "Spend"), ("frequency_tier", "Purchase frequency")):
        for g, r in SA["dimensions"][key]["tiers"].items():
            srows.append({"Segment": lab, "Tier": g, "Customer-snapshots": r["n"], "Lapse rate": r["prevalence"], "Flag rate": r["flag_rate"], "Lapsers caught (TPR)": r["tpr"], "False-alarm rate (FPR)": r["fpr"]})
    sdf = pd.DataFrame(srows)
    st.dataframe(sdf.style.format({c: "{:.3f}" for c in sdf.columns if c not in ("Segment", "Tier", "Customer-snapshots")}), hide_index=True, use_container_width=True)
    lowf, highf = SA["dimensions"]["frequency_tier"]["tiers"]["Low"], SA["dimensions"]["frequency_tier"]["tiers"]["High"]
    st.markdown(f"At the fixed threshold the model flags almost every customer in the lowest purchase-frequency tier (flag rate {lowf['flag_rate']:.3f}), so inside that tier the flag does not separate lapsers from stayers. In the highest-frequency tier it catches {highf['tpr']:.3f} of lapsers. A single threshold behaves very differently by customer type, so Marketing should review it by segment. No claim of fairness is made.")
    with st.expander("Plain-language definitions"):
        st.markdown("""- **Demographic parity difference:** the gap between two groups' flag rates. Zero means both groups are flagged equally often.
- **Disparate impact ratio:** one group's flag rate divided by the other's. The project accepts 0.80 to 1.25.
- **Equalised odds:** among customers with the same real outcome, the model should flag both groups at the same rate. It is checked through the lapsers-caught gap (TPR) and the false-alarm gap (FPR).""")
    st.subheader("Transparency statement")
    st.markdown(f"""- **Intended use:** {M['intended_use']}.
- **Not for:** {'; '.join(M['not_for'])}.
- **Human oversight:** a person reviews every list before any campaign. The model's flags are advisory and should never trigger automatic offers, exclusions or pricing decisions.
- **What not to infer:** a score is not a certainty, not a cause, and not a statement about any customer's character. The fairness figures do not establish that the model is fair.
- **Privacy:** customers are pseudonymised, which is not anonymous. This dashboard stores no customer-level records and the API logs no request bodies.
- **Unresolved:** the protected-attribute requirement cannot be assessed with this data; the non-UK group is small (715 snapshots), so its results are uncertain and monitored.""")

# ------------------------------------------------------------------ 5. about
else:
    st.title("About and evidence")
    st.markdown(f"""**Project.** Retail Analytics Decision Support Platform (BAN 6800, Nexford University, MSc Data Analytics). Author: Bezzel Chitsungo. Task: 90-day customer churn (Module 4), communicated to Marketing and CRM managers (Module 5).""")
    st.subheader("Provenance")
    prov = pd.DataFrame([["Model", f"{M['model_name']} v{M['model_version']}", f"sha-256 prefix {M['model_sha256_16']}"], ["Training / validation / test", "Jun-Dec 2010 / Mar-Apr 2011 / Aug-Sep 2011", "90-day purge between splits"],
                         ["Dataset hash", M["dataset_hash"], "Module 3 published fact table"], ["MLflow runs", f"validation {M['mlflow']['validation_run_id'][:8]}..., test {M['mlflow']['test_run_id'][:8]}...", "experiment retail-churn-90d"],
                         ["Model registry", f"{M['registry']['registered_model']} version {M['registry']['version']} (alias {M['registry']['alias']})", "alias is not production approval"]], columns=["Item", "Value", "Note"])
    st.dataframe(prov, hide_index=True, use_container_width=True)
    st.subheader("Sensitivity of the model (static)")
    sens = pd.DataFrame(E["sensitivity"])[["perturbation", "auc", "delta_auc", "flag_flip_rate"]].rename(columns={"perturbation": "Perturbation", "auc": "Test AUC", "delta_auc": "Change in AUC", "flag_flip_rate": "Flags that flip"})
    st.dataframe(sens.style.format({"Test AUC": "{:.4f}", "Change in AUC": "{:+.4f}", "Flags that flip": "{:.1%}"}), hide_index=True, use_container_width=True)
    st.caption("Noise and shifts of this size barely change ranking quality. This tests robustness to input noise; it does not test robustness to a change in customer behaviour.")
    st.subheader("Limitations")
    st.markdown("""1. The 90-day churn window and the 180-day history rule were agreed with the Marketing Director on 1 November 2026 (confirmed by email from the Marketing Director). The rule includes customers who have not bought for a long time (54% of test snapshots).
2. The test set was scored four times (two iterations under the earlier eligibility rule, one discarded run with a data error, and the final run) plus exploratory checks; this is disclosed in the Validation Report.
3. The lapse rate differs by period (47% training, 62% validation, 60% test), so scores are for ranking and thresholds need review.
4. The model is weaker on customers unseen in training (AUC 0.772 against 0.816). One test window only; no external validation or drift evidence.
5. No protected attributes in the data; the fairness view is an operational UK vs non-UK comparison on a small non-UK group.
6. No measured business or financial impact exists. Any effect on retention is a **hypothesis requiring evaluation**.""")
    st.subheader("Links")
    st.markdown(f"- Source code and documents: [{REPO}]({REPO}) (Model Card in `docs/MODEL_CARD.md`; Validation Report and Fairness Metrics Report in `reports/`)")
    st.subheader("References")
    st.markdown("""- Chen, D. (2019). *Online Retail II* [Data set]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
- Hardt, M., Price, E., & Srebro, N. (2016). Equality of opportunity in supervised learning. *Advances in Neural Information Processing Systems, 29*, 3315-3323.
- Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. *Knowledge and Information Systems, 33*(1), 1-33. https://doi.org/10.1007/s10115-011-0463-8
- Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. *Advances in Neural Information Processing Systems, 30*, 4765-4774.
- Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. *Proceedings of the Conference on Fairness, Accountability, and Transparency*, 220-229. https://doi.org/10.1145/3287560.3287596
- Weerts, H., Dudik, M., Edgar, R., Jalali, A., Lutz, R., & Madaio, M. (2023). Fairlearn: Assessing and improving fairness of AI systems. *Journal of Machine Learning Research, 24*(257), 1-8.""")
    st.caption(f"Evidence file built from Module 4 outputs; dashboard built 31 October 2026. References are in APA 7 style.")
