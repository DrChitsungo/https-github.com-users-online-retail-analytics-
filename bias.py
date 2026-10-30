"""Bias / representation detection suite.

SCOPE AND HONESTY
  * The dataset contains no demographic or protected-characteristic fields and none are inferred.
    Country is the only group attribute; it is a business/geographic attribute, not a demographic one.
  * No external population benchmark exists. Findings are therefore INTERNAL REPRESENTATION IMBALANCE
    (relative to the dataset's own overall rates and to equal calendar coverage), not proof of
    population bias and not a demographic-fairness assessment.
  * Ratio bands are screening heuristics set in configs/pipeline.yaml, not legal tests. Ratios are only
    evaluated for groups with at least `min_group_invoices` invoices, and flags additionally require the
    group's 95% Wilson interval to exclude the overall rate.
  * Bias findings are WARNINGS. They never block publication; they travel with the data as a report.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def _rate_table(inv: pd.DataFrame, group: str, flag_col: str, overall: float, band, min_n: int) -> list[dict]:
    rows = []
    for g, sub in inv.groupby(group, observed=True):
        n, k = len(sub), int(sub[flag_col].sum())
        rate = k / n if n else float("nan")
        lo, hi = wilson(k, n)
        ratio = rate / overall if overall else float("nan")
        evaluable = n >= min_n
        outside = bool(evaluable and (ratio < band[0] or ratio > band[1]))
        ci_excl = bool(evaluable and (overall < lo or overall > hi))
        rows.append({"group": str(g), "invoices": n, "events": k, "rate": round(rate, 4), "ci95": [round(lo, 4), round(hi, 4)],
                     "ratio_to_overall": round(ratio, 3), "evaluable": evaluable, "flag": bool(outside and ci_excl),
                     "note": "" if evaluable else f"fewer than {min_n} invoices: not evaluated"})
    return sorted(rows, key=lambda r: -r["invoices"])


def build_bias_report(cfg: dict, disp: pd.DataFrame, fact: pd.DataFrame) -> dict:
    b = cfg["bias"]
    band, min_n = b["ratio_band"], b["min_group_invoices"]
    rep: dict = {"scope": {
        "group_attributes_available": ["Country"],
        "protected_characteristics_available": [],
        "statement": "Internal representation imbalance only; no demographic fairness claim is possible from this dataset.",
        "thresholds": b,
    }}

    # ---- invoice-level frame (retained records)
    inv = fact.groupby("invoice_no").agg(
        country=("country", "first"), identified=("customer_identified", "max"), is_cancel=("is_cancellation", "max"),
        revenue=("line_revenue", "sum"), lines=("line_id", "size"), first_ts=("invoice_ts", "min")).reset_index()
    inv["month"] = inv["first_ts"].dt.to_period("M").astype(str)
    sales_inv = inv[~inv["is_cancel"]]

    # ---- A. country representation
    g = fact.groupby("country")
    gross = fact[~fact["is_cancellation"]].groupby("country")["line_revenue"].sum()
    tab = pd.DataFrame({
        "lines": g.size(), "invoices": inv.groupby("country").size(), "gross_sales_revenue": gross,
        "identified_customers": fact[fact.customer_identified].groupby("country")["customer_key"].nunique(),
    }).fillna(0)
    for c in ["lines", "invoices", "identified_customers"]:
        tab[c] = tab[c].astype(int)
    tab["share_lines"] = tab["lines"] / tab["lines"].sum()
    tab["share_invoices"] = tab["invoices"] / tab["invoices"].sum()
    tab["share_revenue"] = tab["gross_sales_revenue"] / tab["gross_sales_revenue"].sum()
    tab["share_identified_customers"] = tab["identified_customers"] / tab["identified_customers"].sum()
    tab["thin"] = tab["share_lines"] < b["thin_group_share"]
    tab["dominant"] = tab["share_lines"] > b["dominant_group_share"]
    tab["small_cell"] = tab["identified_customers"] < cfg["privacy"]["small_cell_threshold"]
    tab = tab.sort_values("lines", ascending=False)
    hhi = float(((tab["invoices"] / tab["invoices"].sum()) ** 2).sum())
    rep["country_representation"] = {
        "n_countries": int(len(tab)), "top1_country": str(tab.index[0]), "top1_share_lines": round(float(tab["share_lines"].iloc[0]), 4),
        "top1_share_revenue": round(float(tab["share_revenue"].iloc[0]), 4),
        "top3_share_lines": round(float(tab["share_lines"].iloc[:3].sum()), 4),
        "hhi_invoices": round(hhi, 4), "effective_number_of_countries": round(1 / hhi, 2),
        "countries_thin": int(tab["thin"].sum()), "countries_small_cell": int(tab["small_cell"].sum()),
        "small_cell_countries": [str(x) for x in tab.index[tab["small_cell"]]],
        "table": [{"country": str(i), **{k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else (bool(v) if isinstance(v, (bool, np.bool_)) else int(v))) for k, v in r.items()}} for i, r in tab.iterrows()],
    }

    # ---- B. customer-identification coverage (invoice level)
    overall_id = float(inv["identified"].mean())
    rep["customer_identification_coverage"] = {
        "overall_invoice_rate": round(overall_id, 4),
        "overall_line_rate": round(float(fact["customer_identified"].mean()), 4),
        "revenue_share_unidentified": round(float(fact.loc[~fact.customer_identified, "line_revenue"].sum() / fact["line_revenue"].sum()), 4),
        "by_country": _rate_table(inv, "country", "identified", overall_id, band, min_n),
        "by_month": _rate_table(inv, "month", "identified", overall_id, band, 1),
        "by_cancellation": _rate_table(inv.assign(grp=np.where(inv.is_cancel, "cancellation", "sale")), "grp", "identified", overall_id, band, min_n),
        "identified_vs_unidentified_sales_invoices": {
            "mean_invoice_revenue_identified": round(float(sales_inv.loc[sales_inv.identified, "revenue"].mean()), 2),
            "mean_invoice_revenue_unidentified": round(float(sales_inv.loc[~sales_inv.identified, "revenue"].mean()), 2),
            "mean_lines_identified": round(float(sales_inv.loc[sales_inv.identified, "lines"].mean()), 2),
            "mean_lines_unidentified": round(float(sales_inv.loc[~sales_inv.identified, "lines"].mean()), 2),
        },
    }

    # ---- C. cancellation patterns (invoice level)
    overall_c = float(inv["is_cancel"].mean())
    rep["cancellation_patterns"] = {
        "overall_invoice_rate": round(overall_c, 4),
        "by_country": _rate_table(inv, "country", "is_cancel", overall_c, band, min_n),
        "by_identification": _rate_table(inv.assign(grp=np.where(inv.identified, "identified", "unidentified")), "grp", "is_cancel", overall_c, band, min_n),
        "by_month": _rate_table(inv, "month", "is_cancel", overall_c, band, 1),
        "cancellations_with_original_invoice_in_data": "0% of cancellation invoice numbers match any other invoice number (verified in profiling); cancellations cannot be linked to the sale they reverse.",
    }

    # ---- D. time coverage
    days = fact.groupby(fact["invoice_date"].dt.to_period("M").astype(str))["invoice_date"].nunique().rename("days_observed")
    m = sales_inv.groupby("month").agg(sales_invoices=("revenue", "size"), gross_revenue=("revenue", "sum")).join(days, how="outer").fillna(0)
    lo, hi = fact["invoice_date"].min(), fact["invoice_date"].max()
    idx = pd.PeriodIndex(m.index, freq="M")
    start, end = idx.start_time, idx.end_time.normalize()
    m["partial"] = np.asarray((start < lo) | (end > hi))
    cal = pd.Series(idx.month, index=m.index).value_counts().sort_index()
    q4 = float(m.loc[[i for i in m.index if int(i[5:7]) >= 10], "gross_revenue"].sum() / m["gross_revenue"].sum())
    rep["time_coverage"] = {
        "first_date": str(lo.date()), "last_date": str(hi.date()), "months_spanned": int(len(m)),
        "partial_months": [str(i) for i in m.index[m["partial"]]],
        "calendar_month_repetitions": {int(k): int(v) for k, v in cal.items()},
        "months_covered_three_times": [int(k) for k, v in cal.items() if v >= 3],
        "q4_share_of_gross_revenue": round(q4, 4),
        "monthly": [{"month": i, "sales_invoices": int(r.sales_invoices), "gross_revenue": round(float(r.gross_revenue), 2),
                     "days_observed": int(r.days_observed), "partial": bool(r.partial)} for i, r in m.iterrows()],
        "note": "Only about two annual cycles are observed; seasonality estimates rest on two (December: three) repetitions.",
    }

    # ---- E. cleaning impact by group (raw vs retained)
    raw_c = disp.groupby("country").agg(raw_lines=("raw_row_id", "size"), raw_invoices=("invoice_no", "nunique"))
    ret_c = disp[disp.disposition == "retained"].groupby("country").size().rename("retained_lines")
    ci = raw_c.join(ret_c).fillna(0)
    ci["removal_rate"] = 1 - ci["retained_lines"] / ci["raw_lines"]
    ci["raw_share"] = ci["raw_lines"] / ci["raw_lines"].sum()
    ci["retained_share"] = ci["retained_lines"] / ci["retained_lines"].sum()
    ci["share_ratio"] = ci["retained_share"] / ci["raw_share"]
    ci["evaluable"] = ci["raw_invoices"] >= min_n
    ci["flag"] = ci["evaluable"] & ((ci["share_ratio"] < b["removal_ratio_band"][0]) | (ci["share_ratio"] > b["removal_ratio_band"][1]))
    ci = ci.sort_values("raw_lines", ascending=False)
    ident = disp.groupby("customer_identified").agg(raw_lines=("raw_row_id", "size"), retained=("disposition", lambda s: int((s == "retained").sum())))
    ident["removal_rate"] = 1 - ident["retained"] / ident["raw_lines"]
    rep["cleaning_impact"] = {
        "overall_removal_rate": round(float(1 - (disp.disposition == "retained").mean()), 4),
        "removal_rate_by_identification": {("identified" if k else "unidentified"): round(float(v), 4) for k, v in ident["removal_rate"].items()},
        "countries_flagged": [str(i) for i in ci.index[ci["flag"]]],
        "by_country": [{"country": str(i), "raw_lines": int(r.raw_lines), "raw_invoices": int(r.raw_invoices), "retained_lines": int(r.retained_lines),
                        "removal_rate": round(float(r.removal_rate), 4), "share_ratio": round(float(r.share_ratio), 3),
                        "evaluable": bool(r.evaluable), "flag": bool(r.flag)} for i, r in ci.iterrows()],
        "removal_by_reason": disp.loc[disp.disposition != "retained", "reason_code"].value_counts().to_dict(),
    }

    # ---- findings (measured) -----------------------------------------------------------------
    cr, idc, cp, tc, cim = (rep["country_representation"], rep["customer_identification_coverage"], rep["cancellation_patterns"],
                            rep["time_coverage"], rep["cleaning_impact"])
    flagged_id = [r["group"] for r in idc["by_country"] if r["flag"]]
    flagged_cn = [r["group"] for r in cp["by_country"] if r["flag"]]
    rep["findings"] = [
        f"{cr['top1_country']} accounts for {cr['top1_share_lines']:.1%} of retained lines and {cr['top1_share_revenue']:.1%} of gross sales revenue; effective number of countries = {cr['effective_number_of_countries']} of {cr['n_countries']}.",
        f"{cr['countries_thin']} of {cr['n_countries']} countries each hold under {b['thin_group_share']:.0%} of lines; {cr['countries_small_cell']} have fewer than {cfg['privacy']['small_cell_threshold']} identified customers.",
        f"Customer ID is present on {idc['overall_line_rate']:.1%} of retained lines and {idc['overall_invoice_rate']:.1%} of retained invoices (unidentified invoices are fewer but much larger); unidentified lines carry {idc['revenue_share_unidentified']:.1%} of net revenue. Countries with flagged identification coverage: {', '.join(flagged_id) or 'none'}.",
        f"Cancellation invoices are {cp['overall_invoice_rate']:.1%} of retained invoices. Countries with flagged cancellation rates: {', '.join(flagged_cn) or 'none'}.",
        f"Partial reporting months: {', '.join(tc['partial_months']) or 'none'}; Q4 (Oct-Dec) holds {tc['q4_share_of_gross_revenue']:.1%} of gross sales revenue.",
        f"Cleaning removes {cim['overall_removal_rate']:.2%} of raw lines overall; removal rate is {cim['removal_rate_by_identification'].get('unidentified', float('nan')):.2%} for unidentified-customer lines vs {cim['removal_rate_by_identification'].get('identified', float('nan')):.2%} for identified. Countries whose share shifts beyond the band: {', '.join(cim['countries_flagged']) or 'none'}.",
    ]
    rep["implications"] = [
        "Aggregate KPIs, forecasts and segments are dominated by the United Kingdom; non-UK results rest on thin samples and should be reported with sample sizes or grouped.",
        "RFM, churn and lifetime-value models can only learn from identified customers; if unidentified purchasing differs, models describe a sub-population.",
        "Two annual cycles (December three) limit seasonality estimates; the final partial month must not be compared with full months.",
        "Cancellations cannot be linked to their original sale, so cancellation rates are invoice-level and not product-return rates.",
    ]
    rep["mitigations"] = [
        "Report all KPIs with group sample sizes; apply a minimum-n rule or group small countries (e.g. 'Other') before charting or modelling.",
        "Keep unidentified-customer transactions in revenue, product and demand analytics; restrict only customer-level models to identified customers and state this coverage.",
        "Flag partial months (dim_date.is_partial_month) and exclude them from month-over-month growth and seasonal fitting.",
        "Evaluate forecast and churn model errors by country group (Module 2 Fairlearn plan) once models exist; this pipeline stage only supplies the representation baseline.",
        "Re-run this suite on every refresh and review flagged groups at the AI Ethics Committee's monthly meeting (Module 1 governance).",
    ]
    rep["limitations"] = [
        "No external benchmark or population reference was available; reference = dataset's own overall rate and equal calendar coverage.",
        "Country is a business attribute; no demographic attributes exist, so demographic fairness is NOT assessed.",
        "Ratio-band thresholds are internal screening heuristics, chosen for documentation and review, not statistical or legal standards.",
    ]
    return rep


def to_markdown(rep: dict) -> str:
    out = ["# Bias / representation report", "", f"_{rep['scope']['statement']}_", "", "## Key findings", ""]
    out += [f"- {f}" for f in rep["findings"]]
    out += ["", "## Implications", ""] + [f"- {x}" for x in rep["implications"]]
    out += ["", "## Mitigations", ""] + [f"- {x}" for x in rep["mitigations"]]
    out += ["", "## Limitations", ""] + [f"- {x}" for x in rep["limitations"]]
    out += ["", "## Top countries (retained lines)", "", "| Country | Lines | Share | Invoices | Identified customers | Thin | Small cell |", "|---|---:|---:|---:|---:|:-:|:-:|"]
    for r in rep["country_representation"]["table"][:12]:
        out.append(f"| {r['country']} | {r['lines']:,} | {r['share_lines']:.2%} | {r['invoices']:,} | {r['identified_customers']:,} | {'Y' if r['thin'] else ''} | {'Y' if r['small_cell'] else ''} |")
    out += ["", "Full tables are in `bias_report.json`."]
    return "\n".join(out) + "\n"
