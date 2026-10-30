"""Schema/parsing rules, verified overlap detection and rule-based record disposition.

Every raw row receives exactly one disposition with a reason code:
  retained    -> valid analytical record (includes legitimate cancellations/returns)
  quarantined -> invalid or unusable record, kept with a reason code for review
  excluded    -> valid but outside analytical scope, or redundant (confirmed duplicate ingestion,
                 non-merchandise ledger lines)
Precedence is the order of REASON_ORDER (first match wins), so counts reconcile exactly.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import privacy

RAW_FIELDS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]

# (code, disposition, description) in precedence order
REASON_ORDER = [
    ("EXC_DUP_OVERLAP", "excluded", "Confirmed duplicate ingestion: record repeated in the overlapping window of the two source blocks"),
    ("QRN_PARSE_FAILURE", "quarantined", "A required field failed numeric/datetime/format parsing"),
    ("EXC_NON_MERCHANDISE", "excluded", "Ledger or service line (postage, fees, manual entries, adjustments, vouchers, test codes)"),
    ("QRN_NEGATIVE_PRICE", "quarantined", "Negative unit price"),
    ("QRN_CANCEL_POSITIVE_QTY", "quarantined", "Cancellation invoice with non-negative quantity"),
    ("QRN_STOCK_ADJUSTMENT", "quarantined", "Negative quantity on a non-cancellation invoice (stock write-off / adjustment, no sale)"),
    ("QRN_ZERO_PRICE", "quarantined", "Zero unit price (no revenue; free issue or unpriced adjustment)"),
    ("QRN_ZERO_QUANTITY", "quarantined", "Zero quantity"),
    ("QRN_MISSING_DESCRIPTION", "quarantined", "Missing product description on a priced line"),
    ("QRN_UNRECOGNISED_STOCKCODE", "quarantined", "Stock code matches neither merchandise nor known non-merchandise patterns"),
    ("EXC_DUP_WITHIN_SOURCE", "excluded", "Exact duplicate within a source block (only when drop_within_source_exact_duplicates is enabled)"),
]
REASON_DISPOSITION = {c: d for c, d, _ in REASON_ORDER}
REASON_DESCRIPTION = {c: t for c, _, t in REASON_ORDER}


def parse(bronze: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Typed view of the raw text fields. Failures become flags, never exceptions."""
    n = len(bronze)
    out = pd.DataFrame({"raw_row_id": bronze["raw_row_id"].to_numpy()})
    out["invoice_no"] = bronze["Invoice"].str.strip().str.upper()
    out["stock_code"] = bronze["StockCode"].str.strip().str.upper()
    out["description"] = privacy.scrub_text(bronze["Description"])
    qty = pd.to_numeric(bronze["Quantity"], errors="coerce")
    out["quantity"] = qty.round().astype("Int64")
    price = pd.to_numeric(bronze["Price"], errors="coerce")
    out["unit_price"] = price.astype("float64")
    out["invoice_ts"] = pd.to_datetime(bronze["InvoiceDate"], format=cfg["source"]["datetime_format"], errors="coerce").astype("datetime64[ns]")
    cust = bronze["Customer ID"]
    cust_ok = cust.isna() | cust.str.fullmatch(r"\d+(\.0+)?").fillna(False)
    out["customer_id_raw"] = pd.to_numeric(cust.str.replace(r"\.0+$", "", regex=True), errors="coerce").astype("Int64")
    out["country"] = bronze["Country"].str.strip()

    bad_qty = qty.isna() | (qty != qty.round())
    bad = (
        bad_qty
        | price.isna()
        | out["invoice_ts"].isna()
        | out["invoice_no"].isna() | (out["invoice_no"] == "")
        | out["stock_code"].isna() | (out["stock_code"] == "")
        | out["country"].isna() | (out["country"] == "")
        | ~cust_ok
    )
    out["parse_error"] = bad.to_numpy()
    assert len(out) == n
    return out


def detect_overlap(bronze: pd.DataFrame, parsed: pd.DataFrame, cfg: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return (source_block, duplicate_overlap_mask, evidence).

    A 'block boundary' is hypothesised from backward steps in InvoiceDate in file order. Rows are flagged as
    duplicate ingestion ONLY if the records in the overlapping time window of the two blocks are identical as
    multisets across all eight raw fields. If the comparison fails, no row is flagged.
    """
    ts = parsed["invoice_ts"]
    steps = np.flatnonzero((ts.diff() < pd.Timedelta(0)).to_numpy())
    n = len(parsed)
    block = np.ones(n, dtype=np.int8)
    ev: dict = {
        "backward_steps_in_file_order": int(len(steps)),
        "expected_backward_steps": cfg["rules"]["overlap"]["expected_backward_steps"],
        "hypothesised_boundary_row_id": None,
        "overlap_window": None,
        "rows_block1_in_window": 0,
        "rows_block2_in_window": 0,
        "multiset_identical": False,
        "invoices_in_window_block1": 0,
        "invoices_in_window_block2": 0,
        "verified": False,
        "action": "none",
    }
    dup = np.zeros(n, dtype=bool)
    if not cfg["rules"]["overlap"]["enabled"] or len(steps) != cfg["rules"]["overlap"]["expected_backward_steps"]:
        ev["action"] = "no rows excluded (overlap check disabled or block structure not as expected)"
        return block, dup, ev

    cut = int(steps[0])
    block[cut:] = 2
    ev["hypothesised_boundary_row_id"] = int(parsed["raw_row_id"].iloc[cut])
    lo, hi = ts.iloc[cut:].min(), ts.iloc[:cut].max()
    ev["overlap_window"] = [str(lo), str(hi)]
    if lo > hi:
        ev["action"] = "no overlap window; nothing excluded"
        return block, dup, ev

    in1 = (block == 1) & (ts >= lo).to_numpy()
    in2 = (block == 2) & (ts <= hi).to_numpy()
    ev["rows_block1_in_window"], ev["rows_block2_in_window"] = int(in1.sum()), int(in2.sum())

    def keys(mask: np.ndarray) -> pd.Series:
        sub = bronze.loc[mask, RAW_FIELDS].fillna("\x00")
        return sub.agg("\x1f".join, axis=1)

    k1, k2 = keys(in1), keys(in2)
    ev["invoices_in_window_block1"] = int(parsed.loc[in1, "invoice_no"].nunique())
    ev["invoices_in_window_block2"] = int(parsed.loc[in2, "invoice_no"].nunique())
    same = len(k1) == len(k2) and bool((k1.value_counts().sort_index().equals(k2.value_counts().sort_index())))
    ev["multiset_identical"] = bool(same)
    ev["verified"] = bool(same)
    if same:
        dup = in2
        ev["action"] = "block-2 rows in the overlap window excluded as confirmed duplicate ingestion (block-1 copies retained)"
    else:
        ev["action"] = "records differ between blocks in the window; NOTHING excluded"
    return block, dup, ev


def classify(parsed: pd.DataFrame, bronze: pd.DataFrame, dup_overlap: np.ndarray, cfg: dict) -> pd.DataFrame:
    """Assign disposition + reason code to every row (first matching rule wins)."""
    r = cfg["rules"]
    sc = parsed["stock_code"].fillna("")
    is_nonmerch = sc.str.contains("|".join(f"(?:{p})" for p in r["non_merchandise_patterns"]), regex=True)
    is_product = sc.str.contains("|".join(f"(?:{p})" for p in r["product_code_patterns"]), regex=True)
    is_cancel = parsed["invoice_no"].fillna("").str.startswith(r["cancellation_invoice_prefix"])
    qty = parsed["quantity"].astype("float64")
    price = parsed["unit_price"]

    conds = {
        "EXC_DUP_OVERLAP": dup_overlap,
        "QRN_PARSE_FAILURE": parsed["parse_error"].to_numpy(),
        "EXC_NON_MERCHANDISE": is_nonmerch.to_numpy(),
        "QRN_NEGATIVE_PRICE": (price < 0).to_numpy(),
        "QRN_CANCEL_POSITIVE_QTY": (is_cancel & (qty >= 0)).to_numpy(),
        "QRN_STOCK_ADJUSTMENT": (~is_cancel & (qty < 0)).to_numpy(),
        "QRN_ZERO_PRICE": (price == 0).to_numpy(),
        "QRN_ZERO_QUANTITY": (qty == 0).to_numpy(),
        "QRN_MISSING_DESCRIPTION": (parsed["description"].isna() & (price > 0)).to_numpy(),
        "QRN_UNRECOGNISED_STOCKCODE": (~is_product & ~is_nonmerch).to_numpy(),
    }
    codes = [c for c, _, _ in REASON_ORDER if c in conds]
    reason = np.select([np.asarray(conds[c], dtype=bool) for c in codes], codes, default="OK")

    # exact duplicates within a source block among rows that would otherwise be retained
    cand = reason == "OK"
    dup_within = np.zeros(len(parsed), dtype=bool)
    if cand.any():
        sub = bronze.loc[cand, RAW_FIELDS].fillna("\x00")
        dup_within[np.flatnonzero(cand)] = sub.duplicated(keep="first").to_numpy()
    if r.get("drop_within_source_exact_duplicates", False):
        reason = np.where(dup_within, "EXC_DUP_WITHIN_SOURCE", reason)

    disp = np.where(reason == "OK", "retained", pd.Series(reason).map(REASON_DISPOSITION).to_numpy())
    res = pd.DataFrame({
        "raw_row_id": parsed["raw_row_id"].to_numpy(),
        "disposition": disp,
        "reason_code": reason,
        "is_exact_duplicate_within_source": dup_within,
        "is_cancellation_invoice": is_cancel.to_numpy(),
    })
    return res
