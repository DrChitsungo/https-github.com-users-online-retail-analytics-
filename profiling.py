"""Source profiler for Online Retail II (read-only; never modifies raw data).

Usage: PYTHONPATH=src python -m retail_pipeline.profiling data/raw/online_retail_II.csv reports/source_profile.json
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(src: str, out: str) -> dict:
    p = Path(src)
    # read everything as string first so parsing failures are measured, not hidden
    raw = pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[""])
    n = len(raw)
    prof = {
        "file": p.name,
        "sha256": sha256(p),
        "bytes": p.stat().st_size,
        "rows": n,
        "columns": list(raw.columns),
    }

    # parsing
    qty = pd.to_numeric(raw["Quantity"], errors="coerce")
    price = pd.to_numeric(raw["Price"], errors="coerce")
    dt = pd.to_datetime(raw["InvoiceDate"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    cust = pd.to_numeric(raw["Customer ID"], errors="coerce")
    prof["parse_failures"] = {
        "Quantity": int((qty.isna() & raw["Quantity"].notna()).sum()),
        "Price": int((price.isna() & raw["Price"].notna()).sum()),
        "InvoiceDate": int((dt.isna() & raw["InvoiceDate"].notna()).sum()),
        "Customer ID": int((cust.isna() & raw["Customer ID"].notna()).sum()),
    }
    prof["missing"] = {c: int(raw[c].isna().sum()) for c in raw.columns}
    prof["date_min"] = str(dt.min())
    prof["date_max"] = str(dt.max())
    prof["distinct"] = {c: int(raw[c].nunique()) for c in raw.columns}

    inv = raw["Invoice"].fillna("")
    is_c = inv.str.startswith("C")
    prof["invoice_prefixes"] = inv.str.extract(r"^([A-Za-z]*)")[0].value_counts().to_dict()
    prof["cancellation_invoices_rows"] = int(is_c.sum())
    prof["cancellation_invoices_distinct"] = int(inv[is_c].nunique())
    prof["cancel_rows_positive_qty"] = int((is_c & (qty > 0)).sum())
    prof["negative_qty_rows"] = int((qty < 0).sum())
    prof["negative_qty_not_C"] = int(((qty < 0) & ~is_c).sum())
    prof["negative_qty_not_C_with_price_zero"] = int(((qty < 0) & ~is_c & (price == 0)).sum())
    prof["zero_qty_rows"] = int((qty == 0).sum())
    prof["zero_price_rows"] = int((price == 0).sum())
    prof["zero_price_missing_customer"] = int(((price == 0) & cust.isna()).sum())
    prof["negative_price_rows"] = int((price < 0).sum())
    prof["negative_price_descriptions"] = raw.loc[price < 0, "Description"].value_counts().head(5).to_dict()
    prof["price_quantiles"] = {str(q): float(price.quantile(q)) for q in [0.5, 0.99, 0.999, 1.0]}
    prof["qty_quantiles"] = {str(q): float(qty.quantile(q)) for q in [0.0, 0.001, 0.5, 0.999, 1.0]}

    # non-merchandise codes
    sc = raw["StockCode"].fillna("")
    pat_product = sc.str.fullmatch(r"\d{5}[A-Za-z]{0,2}")
    nonprod = raw.loc[~pat_product, "StockCode"].str.upper().value_counts()
    prof["stockcode_not_5digit_pattern_rows"] = int((~pat_product).sum())
    prof["stockcode_not_5digit_pattern_top"] = nonprod.head(25).to_dict()
    prof["stockcode_distinct_not_pattern"] = int(nonprod.shape[0])

    # descriptions
    desc = raw["Description"]
    prof["description_leading_trailing_ws"] = int((desc.notna() & (desc != desc.str.strip())).sum())
    prof["description_missing_by_price0"] = int((desc.isna() & (price == 0)).sum())
    per_code = raw.dropna(subset=["Description"]).assign(d=lambda x: x["Description"].str.strip().str.upper()).groupby("StockCode")["d"].nunique()
    prof["stockcodes_with_multiple_descriptions"] = int((per_code > 1).sum())

    # duplicates
    prof["exact_duplicate_rows_extra_copies"] = int(raw.duplicated(keep="first").sum())
    prof["exact_duplicate_rows_involved"] = int(raw.duplicated(keep=False).sum())
    key = ["Invoice", "StockCode"]
    prof["repeated_invoice_stockcode_rows_involved"] = int(raw.duplicated(subset=key, keep=False).sum())
    prof["repeated_invoice_stockcode_nonidentical_rows"] = int(
        raw.duplicated(subset=key, keep=False).sum() - raw.duplicated(keep=False).sum()
    )
    sc_raw = raw["StockCode"].fillna("")
    prof["stockcode_lowercase_rows"] = int((sc_raw != sc_raw.str.upper()).sum())
    prof["stockcode_surrounding_whitespace_rows"] = int((sc_raw != sc_raw.str.strip()).sum())

    # country
    cc = raw["Country"].value_counts()
    prof["country_rows"] = cc.to_dict()
    prof["country_distinct"] = int(cc.shape[0])

    # partial periods
    ym = dt.dt.to_period("M").astype(str)
    prof["rows_by_month"] = ym.value_counts().sort_index().to_dict()
    prof["last_day_rows"] = int((dt.dt.date == dt.max().date()).sum())

    # file order monotonic?
    prof["invoicedate_monotonic_in_file_order"] = bool(dt.is_monotonic_increasing)
    resets = int((dt.diff() < pd.Timedelta(0)).sum())
    prof["invoicedate_backward_steps_in_file_order"] = resets
    if resets:
        idx = dt.index[dt.diff() < pd.Timedelta(0)].tolist()
        prof["invoicedate_backward_step_row_indices_first5"] = idx[:5]
        prof["invoicedate_backward_step_dates_first5"] = [
            [str(dt.iloc[i - 1]), str(dt.iloc[i])] for i in idx[:5]
        ]

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(prof, indent=2, default=str))
    return prof


if __name__ == "__main__":
    p = main(sys.argv[1], sys.argv[2])
    print(json.dumps({k: v for k, v in p.items() if not isinstance(v, dict)}, indent=1, default=str))
