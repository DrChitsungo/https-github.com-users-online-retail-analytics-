"""Great Expectations validation, reconciliation and the publication gate.

Severity model
  critical : invariant violations. Any failed critical expectation BLOCKS publication.
  warning  : data-quality drift worth review. Recorded, never blocks.
Legitimate returns/cancellations are allowed: negative quantity/revenue is valid on 'C' invoices and the
rules only require that the sign and the invoice prefix agree.

Results are saved WITHOUT unexpected-value samples (partial_unexpected_list etc.) so no identifiers or
record samples can leak into reports.
"""
from __future__ import annotations

import json
from pathlib import Path

import great_expectations as gx
import numpy as np
import pandas as pd
from great_expectations import expectations as E

from . import privacy

CRIT, WARN = "critical", "warning"
KEEP_RESULT_KEYS = {"element_count", "unexpected_count", "unexpected_percent", "missing_count", "missing_percent",
                    "unexpected_percent_total", "unexpected_percent_nonmissing", "observed_value"}

BRONZE_COLUMNS = ["raw_row_id", "Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
FACT_COLUMNS = ["line_id", "raw_row_id", "invoice_no", "stock_code", "invoice_ts", "invoice_date", "quantity", "unit_price",
                "line_revenue", "is_cancellation", "customer_key", "customer_identified", "country", "source_block",
                "is_exact_duplicate_within_source"]
DIM_PRODUCT_COLUMNS = ["stock_code", "description", "n_description_variants", "first_sold_date", "last_sold_date", "n_lines", "median_unit_price"]
DIM_CUSTOMER_COLUMNS = ["customer_key", "country_primary", "n_countries", "first_purchase_date", "last_purchase_date", "n_sales_invoices", "n_cancellation_invoices"]
DIM_DATE_COLUMNS = ["date", "year", "month", "iso_year", "iso_week", "week_start", "day_of_week", "is_partial_month"]
AGG_DAILY_COLUMNS = ["invoice_date", "country", "sales_invoices", "sale_lines", "units_sold", "gross_sales_revenue", "cancellation_invoices",
                     "cancellation_lines", "units_cancelled", "cancellation_revenue", "net_revenue"]
AGG_WEEKLY_COLUMNS = ["week_start", "stock_code", "units_sold", "gross_sales_revenue", "n_sales_invoices", "units_cancelled", "cancellation_revenue", "net_units"]
AGG_RFM_COLUMNS = ["customer_key", "first_purchase_date", "last_purchase_date", "frequency_invoices", "monetary_gross", "monetary_net",
                   "n_cancellation_invoices", "recency_days", "snapshot_date"]
DT_TYPES = ["datetime64[ns]", "datetime64[us]", "datetime64[ms]"]
KEY_RE = r"^[0-9a-f]{32}$"


class ValidationBlocked(RuntimeError):
    """Raised when critical validation failures prevent publication."""


def _nn(col, sev=CRIT, mostly=1.0, **kw):
    return E.ExpectColumnValuesToNotBeNull(column=col, mostly=mostly, severity=sev, **kw)


def _true(col, sev=CRIT, **kw):
    return E.ExpectColumnValuesToBeInSet(column=col, value_set=[True], severity=sev, **kw)


# ------------------------------------------------------------------------------------------ suites
def bronze_suite(cfg: dict) -> list:
    v, s = cfg["validation"], cfg["source"]
    return [
        E.ExpectTableColumnsToMatchOrderedList(column_list=BRONZE_COLUMNS, severity=CRIT),
        E.ExpectTableRowCountToBeBetween(min_value=s["min_rows_required"], max_value=5_000_000, severity=CRIT),
        E.ExpectColumnValuesToBeUnique(column="raw_row_id", severity=CRIT),
        *[_nn(c) for c in ["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Country"]],
        E.ExpectColumnValuesToMatchRegex(column="Invoice", regex=r"^[A-Za-z]?\d{6}$", severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="Quantity", regex=r"^-?\d+$", severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="Price", regex=r"^-?\d+(\.\d+)?$", severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="InvoiceDate", regex=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="Customer ID", regex=r"^\d+(\.0+)?$", severity=CRIT),
        # acceptable missingness (warnings): measured 0.41% description, 22.8% customer id at profiling time
        _nn("Description", WARN, mostly=0.99),
        _nn("Customer ID", WARN, mostly=1 - v["max_missing_customer_share_warn"]),
    ]


def fact_suite(cfg: dict) -> list:
    v = cfg["validation"]
    lo, hi = v["expected_date_range"]
    return [
        E.ExpectTableRowCountToBeBetween(min_value=cfg["source"]["min_rows_required"], max_value=5_000_000, severity=CRIT),
        *[_nn(c) for c in ["line_id", "invoice_no", "stock_code", "invoice_ts", "invoice_date", "quantity", "unit_price", "line_revenue",
                           "is_cancellation", "customer_identified", "country", "source_block", "raw_row_id"]],
        E.ExpectColumnValuesToBeUnique(column="line_id", severity=CRIT),
        E.ExpectColumnValuesToBeUnique(column="raw_row_id", severity=CRIT),
        E.ExpectColumnValuesToBeInTypeList(column="invoice_ts", type_list=DT_TYPES, severity=CRIT),
        E.ExpectColumnValuesToBeInTypeList(column="invoice_date", type_list=DT_TYPES, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="unit_price", min_value=0, strict_min=True, max_value=v["max_price_retained"], severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="quantity", min_value=-v["max_abs_quantity"], max_value=v["max_abs_quantity"], severity=CRIT),
        E.ExpectColumnValuesToNotBeInSet(column="quantity", value_set=[0], severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="customer_key", regex=KEY_RE, severity=CRIT),
        E.ExpectColumnValuesToMatchRegex(column="country", regex=r"^\S(?:.*\S)?$", severity=CRIT),
        E.ExpectColumnValuesToBeInSet(column="source_block", value_set=[1, 2], severity=CRIT),
        # helper checks computed in the validation view
        _true("chk_cancel_sign_consistent"), _true("chk_cancel_prefix_consistent"), _true("chk_revenue_formula"),
        _true("chk_ts_in_expected_range"), _true("chk_date_matches_ts"), _true("chk_identified_matches_key"),
        _true("chk_stock_in_dim_product"), _true("chk_customer_in_dim_customer"), _true("chk_date_in_dim_date"),
        # warnings
        _nn("customer_key", WARN, mostly=1 - v["max_missing_customer_share_warn"]),
        E.ExpectColumnMeanToBeBetween(column="is_exact_duplicate_within_source", min_value=0, max_value=v["max_exact_duplicate_share_warn"], severity=WARN),
        E.ExpectColumnValuesToBeBetween(column="unit_price", min_value=0, max_value=1000, strict_min=True, mostly=0.9999, severity=WARN),
    ]


def dim_product_suite(cfg: dict) -> list:
    return [
        E.ExpectColumnValuesToBeUnique(column="stock_code", severity=CRIT), _nn("stock_code"), _nn("description"),
        E.ExpectColumnValuesToBeBetween(column="n_description_variants", min_value=1, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="n_lines", min_value=1, severity=CRIT),
        _true("chk_first_le_last_sold"),
        E.ExpectColumnValuesToNotMatchRegex(column="description", regex=r"[\w.+-]+@[\w-]+\.[\w.]+", severity=CRIT),
        E.ExpectColumnValuesToNotMatchRegex(column="description", regex=r"(?i)\b(?:adjustment|found|counted|checked|sorted|entered)\s+by\s+(?!\[redacted\])\w+", severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="n_description_variants", min_value=1, max_value=3, mostly=0.95, severity=WARN),
    ]


def dim_customer_suite(cfg: dict) -> list:
    return [
        E.ExpectColumnValuesToBeUnique(column="customer_key", severity=CRIT), _nn("customer_key"), _nn("country_primary"),
        E.ExpectColumnValuesToMatchRegex(column="customer_key", regex=KEY_RE, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="n_countries", min_value=1, severity=CRIT),
        _true("chk_first_le_last_purchase"),
        E.ExpectColumnValuesToBeBetween(column="n_countries", min_value=1, max_value=1, mostly=0.99, severity=WARN),
    ]


def dim_date_suite(cfg: dict) -> list:
    return [
        E.ExpectColumnValuesToBeUnique(column="date", severity=CRIT), _nn("date"),
        E.ExpectColumnValuesToBeBetween(column="iso_week", min_value=1, max_value=53, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="day_of_week", min_value=0, max_value=6, severity=CRIT),
        _true("chk_week_start_is_monday"),
    ]


def agg_daily_suite(cfg: dict) -> list:
    return [
        E.ExpectCompoundColumnsToBeUnique(column_list=["invoice_date", "country"], severity=CRIT),
        _nn("invoice_date"), _nn("country"), _nn("net_revenue"),
        *[E.ExpectColumnValuesToBeBetween(column=c, min_value=0, severity=CRIT) for c in
          ["sales_invoices", "sale_lines", "units_sold", "gross_sales_revenue", "cancellation_invoices", "cancellation_lines", "units_cancelled"]],
        E.ExpectColumnValuesToBeBetween(column="cancellation_revenue", max_value=0, severity=CRIT),
        _true("chk_net_equals_gross_plus_cancellation"),
    ]


def agg_weekly_suite(cfg: dict) -> list:
    return [
        E.ExpectCompoundColumnsToBeUnique(column_list=["week_start", "stock_code"], severity=CRIT),
        _nn("week_start"), _nn("stock_code"),
        E.ExpectColumnValuesToBeBetween(column="units_sold", min_value=0, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="units_cancelled", min_value=0, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="gross_sales_revenue", min_value=0, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="cancellation_revenue", max_value=0, severity=CRIT),
        _true("chk_net_units"), _true("chk_week_start_is_monday"), _true("chk_stock_in_dim_product"),
    ]


def agg_rfm_suite(cfg: dict) -> list:
    return [
        E.ExpectColumnValuesToBeUnique(column="customer_key", severity=CRIT), _nn("customer_key"),
        E.ExpectColumnValuesToMatchRegex(column="customer_key", regex=KEY_RE, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="frequency_invoices", min_value=0, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="monetary_gross", min_value=0, severity=CRIT),
        E.ExpectColumnValuesToBeBetween(column="recency_days", min_value=0, severity=CRIT),
        _true("chk_first_le_last_purchase"), _true("chk_customer_in_dim_customer"),
        # customers with only cancellations have no purchase date: acceptable but worth knowing
        _nn("last_purchase_date", WARN, mostly=0.99),
    ]


def recon_suite(cfg: dict) -> list:
    return [
        E.ExpectTableRowCountToBeBetween(min_value=10, max_value=100, severity=CRIT),
        _true("within_tolerance"),
        E.ExpectColumnValuesToBeBetween(column="abs_difference", min_value=0, max_value=cfg["validation"]["tolerance_currency"], severity=CRIT),
    ]


OUTPUT_SCHEMAS = {
    "fact_sales_line": FACT_COLUMNS, "dim_product": DIM_PRODUCT_COLUMNS, "dim_customer": DIM_CUSTOMER_COLUMNS,
    "dim_date": DIM_DATE_COLUMNS, "agg_daily_sales": AGG_DAILY_COLUMNS, "agg_weekly_sku_demand": AGG_WEEKLY_COLUMNS,
    "agg_customer_rfm_base": AGG_RFM_COLUMNS,
}


def _schema_suite(cols):
    # the ACTUAL output table (no helper columns) must have exactly these columns, in this order
    return lambda cfg: [E.ExpectTableColumnsToMatchOrderedList(column_list=cols, severity=CRIT)]


SUITES = {
    **{f"{n}__schema": _schema_suite(c) for n, c in OUTPUT_SCHEMAS.items()},
    "bronze_raw": bronze_suite, "fact_sales_line": fact_suite, "dim_product": dim_product_suite,
    "dim_customer": dim_customer_suite, "dim_date": dim_date_suite, "agg_daily_sales": agg_daily_suite,
    "agg_weekly_sku_demand": agg_weekly_suite, "agg_customer_rfm_base": agg_rfm_suite, "reconciliation": recon_suite,
}


# ------------------------------------------------------------------------------------------ views
def validation_views(cfg: dict, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Copies of the output tables with helper boolean checks (derived columns exist only here)."""
    lo, hi = (pd.Timestamp(x) for x in cfg["validation"]["expected_date_range"])
    f = tables["fact_sales_line"].copy()
    dp, dc, dd = tables["dim_product"], tables["dim_customer"], tables["dim_date"]
    f["chk_cancel_sign_consistent"] = f["is_cancellation"] == (f["quantity"] < 0)
    f["chk_cancel_prefix_consistent"] = f["is_cancellation"] == f["invoice_no"].str.startswith("C")
    f["chk_revenue_formula"] = (f["line_revenue"] - (f["quantity"] * f["unit_price"]).round(4)).abs() <= 1e-6
    f["chk_ts_in_expected_range"] = (f["invoice_ts"] >= lo) & (f["invoice_ts"] < hi + pd.Timedelta(days=1))
    f["chk_date_matches_ts"] = f["invoice_date"] == f["invoice_ts"].dt.normalize()
    f["chk_identified_matches_key"] = f["customer_identified"] == f["customer_key"].notna()
    f["chk_stock_in_dim_product"] = f["stock_code"].isin(set(dp["stock_code"]))
    f["chk_customer_in_dim_customer"] = ~f["customer_identified"] | f["customer_key"].isin(set(dc["customer_key"]))
    f["chk_date_in_dim_date"] = f["invoice_date"].isin(set(dd["date"]))

    p = dp.copy(); p["chk_first_le_last_sold"] = p["first_sold_date"].isna() | (p["first_sold_date"] <= p["last_sold_date"])
    c = dc.copy(); c["chk_first_le_last_purchase"] = c["first_purchase_date"].isna() | (c["first_purchase_date"] <= c["last_purchase_date"])
    d = dd.copy(); d["chk_week_start_is_monday"] = d["week_start"].dt.weekday == 0
    a = tables["agg_daily_sales"].copy()
    a["chk_net_equals_gross_plus_cancellation"] = (a["net_revenue"] - (a["gross_sales_revenue"] + a["cancellation_revenue"])).abs() <= 1e-6
    w = tables["agg_weekly_sku_demand"].copy()
    w["chk_net_units"] = w["net_units"] == (w["units_sold"] - w["units_cancelled"])
    w["chk_week_start_is_monday"] = w["week_start"].dt.weekday == 0
    w["chk_stock_in_dim_product"] = w["stock_code"].isin(set(dp["stock_code"]))
    r = tables["agg_customer_rfm_base"].copy()
    r["chk_first_le_last_purchase"] = r["first_purchase_date"].isna() | (r["first_purchase_date"] <= r["last_purchase_date"])
    r["chk_customer_in_dim_customer"] = r["customer_key"].isin(set(dc["customer_key"]))
    return {"fact_sales_line": f, "dim_product": p, "dim_customer": c, "dim_date": d, "agg_daily_sales": a,
            "agg_weekly_sku_demand": w, "agg_customer_rfm_base": r}


# ------------------------------------------------------------------------------------------ reconciliation
def build_reconciliation(cfg: dict, *, raw_rows: int, raw_revenue_independent: float, disposition: pd.DataFrame,
                         file_rows: dict[str, int], tables: dict[str, pd.DataFrame], overlap_evidence: dict) -> pd.DataFrame:
    tol = cfg["validation"]["tolerance_currency"]
    fact, daily, weekly = tables["fact_sales_line"], tables["agg_daily_sales"], tables["agg_weekly_sku_demand"]
    rfm, dcust = tables["agg_customer_rfm_base"], tables["dim_customer"]
    cnt = disposition["disposition"].value_counts()
    rev = disposition.groupby("disposition")["line_revenue_raw"].sum()
    sales = fact[~fact["is_cancellation"]]
    ident = fact[fact["customer_identified"]]
    rows = [
        ("rows: raw = retained + quarantined + excluded", raw_rows, int(cnt.sum()), 0),
        ("rows: retained partition = fact rows", int(cnt.get("retained", 0)), len(fact), 0),
        ("rows: quarantined partition = quarantine file", int(cnt.get("quarantined", 0)), file_rows["quarantine"], 0),
        ("rows: excluded partition = excluded file", int(cnt.get("excluded", 0)), file_rows["excluded"], 0),
        ("rows: excluded overlap = verified block-2 window rows",
         overlap_evidence["rows_block2_in_window"] if overlap_evidence.get("verified") else 0,
         int((disposition["reason_code"] == "EXC_DUP_OVERLAP").sum()), 0),
        ("revenue: independent raw sum = sum of retained + quarantined + excluded", raw_revenue_independent, float(rev.sum()), tol),
        ("revenue: retained partition = fact line_revenue", float(rev.get("retained", 0.0)), float(fact["line_revenue"].sum()), tol),
        ("revenue: fact = daily net revenue", float(fact["line_revenue"].sum()), float(daily["net_revenue"].sum()), tol),
        ("units: fact net quantity = daily units_sold - units_cancelled", int(fact["quantity"].sum()), int(daily["units_sold"].sum() - daily["units_cancelled"].sum()), 0),
        ("revenue: fact gross sales = weekly SKU gross sales", float(sales["line_revenue"].sum()), float(weekly["gross_sales_revenue"].sum()), tol),
        ("units: fact net quantity = weekly SKU net units", int(fact["quantity"].sum()), int(weekly["net_units"].sum()), 0),
        ("revenue: identified-customer fact revenue = RFM monetary_net", float(ident["line_revenue"].sum()), float(rfm["monetary_net"].sum()), tol),
        ("customers: distinct customer_key in fact = dim_customer rows", int(ident["customer_key"].nunique()), len(dcust), 0),
    ]
    df = pd.DataFrame(rows, columns=["check", "expected", "actual", "tolerance"])
    df["abs_difference"] = (df["expected"].astype(float) - df["actual"].astype(float)).abs().round(6)
    df["within_tolerance"] = df["abs_difference"] <= df["tolerance"].astype(float) + 1e-9
    return df


# ------------------------------------------------------------------------------------------ execution
def _sanitise(result: dict) -> dict:
    return {k: v for k, v in (result or {}).items() if k in KEEP_RESULT_KEYS}


def run_suite(ctx_gx, name: str, df: pd.DataFrame, expectations: list) -> dict:
    ds = ctx_gx.data_sources.add_pandas(name=f"ds_{name}")
    asset = ds.add_dataframe_asset(name=name)
    bd = asset.add_batch_definition_whole_dataframe(f"{name}_whole")
    batch = bd.get_batch(batch_parameters={"dataframe": df})
    suite = gx.ExpectationSuite(name=f"{name}_suite", expectations=expectations)
    raw = batch.validate(suite, result_format="BASIC").to_json_dict()
    items, crit_fail, warn_fail = [], 0, 0
    for r in raw["results"]:
        cfg_ = r["expectation_config"]
        sev = str(cfg_.get("severity", CRIT)).lower().split(".")[-1]
        ok = bool(r["success"])
        if not ok:
            if sev == CRIT:
                crit_fail += 1
            else:
                warn_fail += 1
        kw = cfg_.get("kwargs", {})
        items.append({
            "expectation": cfg_["type"], "column": kw.get("column") or kw.get("column_list"),
            "severity": sev, "success": ok, "mostly": kw.get("mostly"),
            "result": _sanitise(r.get("result")),
        })
    return {
        "suite": name, "rows_validated": int(len(df)), "success": crit_fail == 0 and warn_fail == 0,
        "critical_failures": crit_fail, "warning_failures": warn_fail,
        "expectations_evaluated": len(items), "expectations_passed": sum(i["success"] for i in items), "results": items,
    }


def run_all(cfg: dict, suites_to_run: dict[str, pd.DataFrame]) -> dict:
    gctx = gx.get_context(mode="ephemeral")
    out = [run_suite(gctx, n, df, SUITES[n](cfg)) for n, df in suites_to_run.items()]
    crit = sum(s["critical_failures"] for s in out)
    return {
        "great_expectations_version": gx.__version__,
        "suites": out,
        "critical_failures": crit,
        "warning_failures": sum(s["warning_failures"] for s in out),
        "expectations_evaluated": sum(s["expectations_evaluated"] for s in out),
        "expectations_passed": sum(s["expectations_passed"] for s in out),
        "publish_allowed": crit == 0,
    }


def validate_bronze(cfg: dict, bronze: pd.DataFrame) -> dict:
    return run_all(cfg, {"bronze_raw": bronze})


def validate_outputs(cfg: dict, tables: dict[str, pd.DataFrame], recon: pd.DataFrame) -> dict:
    views = validation_views(cfg, tables)
    schemas = {f"{n}__schema": tables[n] for n in OUTPUT_SCHEMAS}
    res = run_all(cfg, {**schemas, **views, "reconciliation": recon})
    res["reconciliation"] = json.loads(recon.to_json(orient="records"))
    return res


def assert_gate(results: dict, stage: str) -> None:
    if not results["publish_allowed"]:
        failed = [f"{s['suite']}:{i['expectation']}:{i['column']}" for s in results["suites"] for i in s["results"]
                  if not i["success"] and i["severity"] == CRIT]
        raise ValidationBlocked(f"{stage}: {results['critical_failures']} critical expectation(s) failed -> publication blocked. {failed[:8]}")


def export_suites(cfg: dict, out_dir: Path) -> list[str]:
    """Write the (code-defined) suites as JSON for review/versioning in gx/expectations/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for n, fn in SUITES.items():
        suite = gx.ExpectationSuite(name=f"{n}_suite", expectations=fn(cfg))
        (out_dir / f"{n}_suite.json").write_text(json.dumps(suite.to_json_dict(), indent=2, sort_keys=True, default=str))
        names.append(n)
    return names
