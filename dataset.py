"""Build the customer-snapshot modelling table from the Module 3 published fact table (read-only).

Unit of analysis: one identified customer at one prediction date T (a monthly snapshot).
Eligible: >=1 sales invoice in [T - lookback, T).
Features: only invoices dated strictly before T.
Label churn=1: NO sales invoice dated in [T, T + horizon). Snapshots whose outcome window extends past the end of the
data are never created, so incomplete follow-up is not labelled as churn.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np, pandas as pd
from .tracking import ROOT, cfg

FEATURES = [
    "recency_days", "tenure_days", "n_inv_all", "n_inv_30", "n_inv_90", "n_inv_prev90", "is_single_invoice",
    "rev_all", "rev_90", "rev_180", "n_products_all", "n_products_180", "avg_units_per_inv",
    "mean_gap_days", "std_gap_days", "recency_over_gap", "n_cancel_all", "cancel_ratio",
]
EVAL_ONLY = ["customer_key", "snapshot", "country", "group_uk"]   # kept for evaluation; never predictors


def published_dir() -> Path:
    latest = json.loads((ROOT / "data" / "published" / "LATEST.json").read_text())
    return ROOT / "data" / "published" / latest["run_id"]


def fact_path() -> Path:
    return published_dir() / "fact_sales_line.parquet"


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    f = pd.read_parquet(fact_path(), columns=["invoice_no", "invoice_date", "stock_code", "quantity", "line_revenue",
                                              "is_cancellation", "customer_key", "customer_identified", "country"])
    f = f[f.customer_identified].copy()
    f["invoice_date"] = pd.to_datetime(f["invoice_date"]).dt.normalize()
    sales = f[~f.is_cancellation]
    inv = (sales.groupby(["customer_key", "invoice_no"], as_index=False)
                .agg(date=("invoice_date", "first"), revenue=("line_revenue", "sum"), units=("quantity", "sum"),
                     n_products=("stock_code", "nunique"), country=("country", "first")))
    canc = (f[f.is_cancellation].groupby(["customer_key", "invoice_no"], as_index=False).agg(date=("invoice_date", "first")))
    prod = sales[["customer_key", "invoice_date", "stock_code"]].drop_duplicates()
    return inv, canc, prod


def snapshot_dates(c=None):
    c = c or cfg()
    return list(pd.date_range(c["snapshots"]["first"], c["snapshots"]["last"], freq="MS"))


def build_snapshot(T: pd.Timestamp, inv: pd.DataFrame, canc: pd.DataFrame, prod: pd.DataFrame, c=None) -> pd.DataFrame:
    c = c or cfg(); H = c["task"]["horizon_days"]; L = c["task"]["lookback_days"]
    past = inv[inv.date < T]
    active = past[past.date >= T - pd.Timedelta(days=L)].customer_key.unique()
    past = past[past.customer_key.isin(active)].sort_values(["customer_key", "date"])
    g = past.groupby("customer_key")
    d = pd.DataFrame({
        "recency_days": (T - g.date.max()).dt.days, "tenure_days": (T - g.date.min()).dt.days,
        "n_inv_all": g.size(), "rev_all": g.revenue.sum(), "avg_inv_value": g.revenue.mean(), "avg_units_per_inv": g.units.mean(),
    })
    for k in (30, 90, 180):
        w = past[past.date >= T - pd.Timedelta(days=k)].groupby("customer_key")
        d[f"n_inv_{k}"] = w.size(); d[f"rev_{k}"] = w.revenue.sum() if k != 30 else np.nan
    d = d.drop(columns=["rev_30"], errors="ignore")
    p2 = past[(past.date >= T - pd.Timedelta(days=180)) & (past.date < T - pd.Timedelta(days=90))].groupby("customer_key").size()
    d["n_inv_prev90"] = p2
    for col in ("n_inv_30", "n_inv_90", "n_inv_180", "n_inv_prev90", "rev_90", "rev_180"):
        d[col] = d[col].fillna(0)
    pp = prod[(prod.invoice_date < T) & (prod.customer_key.isin(active))]
    d["n_products_all"] = pp.groupby("customer_key").stock_code.nunique()
    d["n_products_180"] = pp[pp.invoice_date >= T - pd.Timedelta(days=180)].groupby("customer_key").stock_code.nunique()
    gaps = past.groupby("customer_key").date.diff().dt.days.dropna()
    gg = gaps.groupby(past.loc[gaps.index, "customer_key"])
    d["mean_gap_days"] = gg.mean(); d["std_gap_days"] = gg.std()
    d["recency_over_gap"] = d.recency_days / d.mean_gap_days.replace(0, np.nan)
    cc = canc[canc.date < T].groupby("customer_key").size()
    d["n_cancel_all"] = cc; d["n_cancel_all"] = d["n_cancel_all"].fillna(0)
    d["cancel_ratio"] = d.n_cancel_all / (d.n_inv_all + d.n_cancel_all)
    d["is_single_invoice"] = (d.n_inv_all == 1).astype(int)
    # label: any sales invoice in [T, T+H)?
    fut = inv[(inv.date >= T) & (inv.date < T + pd.Timedelta(days=H))].customer_key.unique()
    d["churn"] = (~d.index.isin(fut)).astype(int)
    last_country = past.groupby("customer_key").country.last()
    d["country"] = last_country; d["group_uk"] = np.where(d.country == "United Kingdom", "UK", "Non-UK")
    d["snapshot"] = T
    d = d.reset_index().rename(columns={"index": "customer_key"})
    return d


def build_all(c=None) -> pd.DataFrame:
    c = c or cfg()
    inv, canc, prod = load_events()
    parts = [build_snapshot(T, inv, canc, prod, c) for T in snapshot_dates(c)]
    df = pd.concat(parts, ignore_index=True)
    return df[EVAL_ONLY + FEATURES + ["churn"]]


def split_masks(df: pd.DataFrame, c=None):
    c = c or cfg()
    def m(a, b):
        return (df.snapshot >= pd.Timestamp(a)) & (df.snapshot <= pd.Timestamp(b))
    s = c["split"]
    return {k: m(*s[k]) for k in ("train", "validation", "test")}
