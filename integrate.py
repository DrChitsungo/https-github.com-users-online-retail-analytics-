"""Integration: one cleaned source is organised into a star-style model (dimensions, fact, aggregates).

No additional sources are invented. 'Integration' here means conforming the single cleaned transaction
stream into documented keys and grains that analytics consumers share.

Tables and grain
  fact_sales_line          one retained invoice line                         PK line_id
  dim_product              one merchandise stock code                        PK stock_code
  dim_customer             one pseudonymised customer                        PK customer_key
  dim_date                 one calendar day                                  PK date
  agg_daily_sales          one calendar day x country                        PK (invoice_date, country)
  agg_weekly_sku_demand    one ISO week (Monday start) x stock code          PK (week_start, stock_code), sparse
  agg_customer_rfm_base    one pseudonymised customer                        PK customer_key
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _mode_text(df: pd.DataFrame, key: str, col: str) -> pd.Series:
    """Most frequent value per key; ties broken alphabetically so results are deterministic."""
    cnt = df.groupby([key, col], dropna=True).size().rename("n").reset_index()
    cnt = cnt.sort_values([key, "n", col], ascending=[True, False, True], kind="stable")
    return cnt.drop_duplicates(key).set_index(key)[col]


def build_dim_product(fact: pd.DataFrame, retained: pd.DataFrame) -> pd.DataFrame:
    d = retained[["stock_code", "description"]].copy()
    d["description"] = d["description"].str.upper()
    canon = _mode_text(d, "stock_code", "description")
    variants = d.groupby("stock_code")["description"].nunique().rename("n_description_variants")
    g = fact.groupby("stock_code")
    sales = fact[~fact["is_cancellation"]]
    dim = pd.DataFrame({
        "description": canon,
        "n_description_variants": variants,
        "first_sold_date": sales.groupby("stock_code")["invoice_date"].min(),
        "last_sold_date": sales.groupby("stock_code")["invoice_date"].max(),
        "n_lines": g.size(),
        "median_unit_price": sales.groupby("stock_code")["unit_price"].median(),
    })
    dim = dim.reindex(sorted(fact["stock_code"].unique()))
    dim.index.name = "stock_code"
    dim["n_description_variants"] = dim["n_description_variants"].astype("int64")
    dim["n_lines"] = dim["n_lines"].astype("int64")
    return dim.reset_index()


def build_dim_customer(fact: pd.DataFrame) -> pd.DataFrame:
    f = fact[fact["customer_identified"]].copy()
    country = _mode_text(f, "customer_key", "country").rename("country_primary")
    sales = f[~f["is_cancellation"]]
    g = f.groupby("customer_key")
    dim = pd.DataFrame({
        "country_primary": country,
        "n_countries": g["country"].nunique().astype("int64"),
        "first_purchase_date": sales.groupby("customer_key")["invoice_date"].min(),
        "last_purchase_date": sales.groupby("customer_key")["invoice_date"].max(),
        "n_sales_invoices": sales.groupby("customer_key")["invoice_no"].nunique(),
        "n_cancellation_invoices": f[f["is_cancellation"]].groupby("customer_key")["invoice_no"].nunique(),
    }).sort_index()
    dim["n_sales_invoices"] = dim["n_sales_invoices"].fillna(0).astype("int64")
    dim["n_cancellation_invoices"] = dim["n_cancellation_invoices"].fillna(0).astype("int64")
    dim.index.name = "customer_key"
    return dim.reset_index()


def build_dim_date(fact: pd.DataFrame) -> pd.DataFrame:
    lo, hi = fact["invoice_date"].min(), fact["invoice_date"].max()
    days = pd.date_range(lo, hi, freq="D")
    iso = days.isocalendar()
    d = pd.DataFrame({
        "date": days,
        "year": days.year.astype("int64"),
        "month": days.month.astype("int64"),
        "iso_year": iso["year"].astype("int64").to_numpy(),
        "iso_week": iso["week"].astype("int64").to_numpy(),
        "week_start": days - pd.to_timedelta(days.weekday, unit="D"),
        "day_of_week": days.weekday.astype("int64"),
    })
    month_start = d["date"] - pd.to_timedelta(d["date"].dt.day - 1, unit="D")
    month_end = month_start + pd.offsets.MonthEnd(0)
    d["is_partial_month"] = ((month_start < lo) | (month_end > hi)).to_numpy()
    return d


def build_agg_daily(fact: pd.DataFrame) -> pd.DataFrame:
    sale = fact[~fact["is_cancellation"]]
    canc = fact[fact["is_cancellation"]]
    keys = ["invoice_date", "country"]
    a = sale.groupby(keys).agg(
        sales_invoices=("invoice_no", "nunique"), sale_lines=("line_id", "size"),
        units_sold=("quantity", "sum"), gross_sales_revenue=("line_revenue", "sum"))
    b = canc.groupby(keys).agg(
        cancellation_invoices=("invoice_no", "nunique"), cancellation_lines=("line_id", "size"),
        units_cancelled=("quantity", lambda s: -int(s.sum())), cancellation_revenue=("line_revenue", "sum"))
    out = a.join(b, how="outer").fillna(0).reset_index()
    for c in ["sales_invoices", "sale_lines", "units_sold", "cancellation_invoices", "cancellation_lines", "units_cancelled"]:
        out[c] = out[c].astype("int64")
    out["gross_sales_revenue"] = out["gross_sales_revenue"].round(4)
    out["cancellation_revenue"] = out["cancellation_revenue"].round(4)
    out["net_revenue"] = (out["gross_sales_revenue"] + out["cancellation_revenue"]).round(4)
    return out.sort_values(keys, kind="stable").reset_index(drop=True)


def build_agg_weekly_sku(fact: pd.DataFrame) -> pd.DataFrame:
    f = fact.copy()
    f["week_start"] = f["invoice_date"] - pd.to_timedelta(f["invoice_date"].dt.weekday, unit="D")
    sale = f[~f["is_cancellation"]]
    canc = f[f["is_cancellation"]]
    keys = ["week_start", "stock_code"]
    a = sale.groupby(keys).agg(units_sold=("quantity", "sum"), gross_sales_revenue=("line_revenue", "sum"),
                               n_sales_invoices=("invoice_no", "nunique"))
    b = canc.groupby(keys).agg(units_cancelled=("quantity", lambda s: -int(s.sum())), cancellation_revenue=("line_revenue", "sum"))
    out = a.join(b, how="outer").fillna(0).reset_index()
    for c in ["units_sold", "n_sales_invoices", "units_cancelled"]:
        out[c] = out[c].astype("int64")
    out["net_units"] = out["units_sold"] - out["units_cancelled"]
    out["gross_sales_revenue"] = out["gross_sales_revenue"].round(4)
    out["cancellation_revenue"] = out["cancellation_revenue"].round(4)
    return out.sort_values(keys, kind="stable").reset_index(drop=True)


def build_agg_rfm_base(fact: pd.DataFrame) -> pd.DataFrame:
    f = fact[fact["customer_identified"]]
    snapshot = fact["invoice_date"].max() + pd.Timedelta(days=1)
    sale = f[~f["is_cancellation"]]
    g = f.groupby("customer_key")
    out = pd.DataFrame({
        "first_purchase_date": sale.groupby("customer_key")["invoice_date"].min(),
        "last_purchase_date": sale.groupby("customer_key")["invoice_date"].max(),
        "frequency_invoices": sale.groupby("customer_key")["invoice_no"].nunique(),
        "monetary_gross": sale.groupby("customer_key")["line_revenue"].sum(),
        "monetary_net": g["line_revenue"].sum(),
        "n_cancellation_invoices": f[f["is_cancellation"]].groupby("customer_key")["invoice_no"].nunique(),
    }).sort_index()
    out["frequency_invoices"] = out["frequency_invoices"].fillna(0).astype("int64")
    out["monetary_gross"] = out["monetary_gross"].fillna(0.0).round(4)
    out["monetary_net"] = out["monetary_net"].round(4)
    out["n_cancellation_invoices"] = out["n_cancellation_invoices"].fillna(0).astype("int64")
    out["recency_days"] = (snapshot - out["last_purchase_date"]).dt.days.astype("Int64")
    out["snapshot_date"] = snapshot
    out.index.name = "customer_key"
    return out.reset_index()


def integrate(fact: pd.DataFrame, retained: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "fact_sales_line": fact,
        "dim_product": build_dim_product(fact, retained),
        "dim_customer": build_dim_customer(fact),
        "dim_date": build_dim_date(fact),
        "agg_daily_sales": build_agg_daily(fact),
        "agg_weekly_sku_demand": build_agg_weekly_sku(fact),
        "agg_customer_rfm_base": build_agg_rfm_base(fact),
    }
