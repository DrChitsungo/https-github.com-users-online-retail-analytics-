"""Cleaning orchestration (bronze -> silver) and business transformations (silver -> fact)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import cleaning, privacy
from .config import RunContext

FACT_COLUMNS = [
    "line_id", "raw_row_id", "invoice_no", "stock_code", "invoice_ts", "invoice_date", "quantity",
    "unit_price", "line_revenue", "is_cancellation", "customer_key", "customer_identified", "country",
    "source_block", "is_exact_duplicate_within_source",
]


def build_silver(cfg: dict, ctx: RunContext, bronze_path: Path, secret: bytes) -> dict:
    """Parse, classify, pseudonymise. The raw Customer ID never leaves this function."""
    bronze = pd.read_parquet(bronze_path)
    n_raw = len(bronze)
    staff_rows_raw = int(bronze["Description"].dropna().str.contains(privacy._PATTERNS["staff_name_after_by"], regex=True).sum())

    parsed = cleaning.parse(bronze, cfg)
    block, dup_overlap, overlap_ev = cleaning.detect_overlap(bronze, parsed, cfg)
    disp = cleaning.classify(parsed, bronze, dup_overlap, cfg)

    parsed["source_block"] = block
    parsed["customer_key"] = privacy.pseudonymise_ids(parsed["customer_id_raw"], secret, cfg["privacy"]["pseudonym_hex_length"])
    parsed["customer_identified"] = parsed["customer_key"].notna()
    parsed["line_revenue_raw"] = (parsed["quantity"].astype("float64") * parsed["unit_price"])
    parsed = parsed.drop(columns=["customer_id_raw"])  # raw identifier dropped here
    for c in ("disposition", "reason_code", "is_exact_duplicate_within_source", "is_cancellation_invoice"):
        parsed[c] = disp[c].to_numpy()

    out = ctx.run_dir / "silver"
    out.mkdir(parents=True, exist_ok=True)
    narrow = ["raw_row_id", "invoice_no", "stock_code", "invoice_ts", "country", "quantity", "unit_price",
              "line_revenue_raw", "customer_identified", "source_block", "disposition", "reason_code",
              "is_cancellation_invoice", "is_exact_duplicate_within_source"]
    parsed[narrow].to_parquet(out / "row_disposition.parquet", index=False)
    wide = narrow + ["description", "customer_key"]
    parsed.loc[parsed.disposition == "retained", wide].to_parquet(out / "retained.parquet", index=False)
    parsed.loc[parsed.disposition == "quarantined", wide].to_parquet(out / "quarantine.parquet", index=False)
    parsed.loc[parsed.disposition == "excluded", wide].to_parquet(out / "excluded.parquet", index=False)

    counts = parsed["reason_code"].value_counts().sort_index().to_dict()
    rev = parsed.groupby("reason_code")["line_revenue_raw"].sum().round(2).to_dict()
    summary = {
        "rows_raw": int(n_raw),
        "rows_retained": int((parsed.disposition == "retained").sum()),
        "rows_quarantined": int((parsed.disposition == "quarantined").sum()),
        "rows_excluded": int((parsed.disposition == "excluded").sum()),
        "reason_counts": {k: int(v) for k, v in counts.items()},
        "reason_revenue": {k: float(v) for k, v in rev.items()},
        "retained_exact_duplicate_rows_flagged": int(parsed.loc[parsed.disposition == "retained", "is_exact_duplicate_within_source"].sum()),
        "overlap_evidence": overlap_ev,
        "staff_name_pattern_rows_raw": staff_rows_raw,
        "stock_code_case_normalised_rows": int((bronze["StockCode"].str.strip() != bronze["StockCode"].str.strip().str.upper()).sum()),
        "reason_descriptions": cleaning.REASON_DESCRIPTION,
    }
    (ctx.report_dir).mkdir(parents=True, exist_ok=True)
    (ctx.report_dir / "cleaning_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    summary["silver_dir"] = str(out)
    return summary


def build_fact(cfg: dict, ctx: RunContext, silver_dir: Path) -> pd.DataFrame:
    """Business transformations on retained records: line revenue, cancellation flag, deterministic line key."""
    r = pd.read_parquet(silver_dir / "retained.parquet").sort_values("raw_row_id", kind="stable").reset_index(drop=True)
    seq = r.groupby("invoice_no").cumcount() + 1
    fact = pd.DataFrame({
        "line_id": r["invoice_no"] + "-" + seq.astype(str).str.zfill(4),
        "raw_row_id": r["raw_row_id"].astype("int64"),
        "invoice_no": r["invoice_no"],
        "stock_code": r["stock_code"],
        "invoice_ts": r["invoice_ts"],
        "invoice_date": r["invoice_ts"].dt.normalize(),
        "quantity": r["quantity"].astype("int64"),
        "unit_price": r["unit_price"].astype("float64"),
        "line_revenue": (r["quantity"].astype("float64") * r["unit_price"]).round(4),
        "is_cancellation": r["is_cancellation_invoice"].astype(bool),
        "customer_key": r["customer_key"].astype("string"),
        "customer_identified": r["customer_identified"].astype(bool),
        "country": r["country"],
        "source_block": r["source_block"].astype("int8"),
        "is_exact_duplicate_within_source": r["is_exact_duplicate_within_source"].astype(bool),
    })[FACT_COLUMNS]
    return fact
