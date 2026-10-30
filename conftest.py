"""Shared fixtures. All rows below are hand-written UNIT-TEST FIXTURES, not dataset records, and are never
used to supplement the real Online Retail II data. Real data is only used by the pipeline run itself."""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["CUSTOMER_KEY_SECRET"] = "unit-test-secret-" + "x" * 32  # test-only value

from retail_pipeline import config  # noqa: E402

RAW_COLS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]


@pytest.fixture(scope="session")
def cfg():
    c = config.load_config()
    c["source"]["expected_sha256"] = None
    c["source"]["min_rows_required"] = 10
    return c


def bronze_from(rows):
    """rows: list of 8-tuples of raw strings (None = missing). Adds raw_row_id like ingestion does."""
    df = pd.DataFrame(rows, columns=RAW_COLS, dtype="object").astype("string")
    df.insert(0, "raw_row_id", range(len(df)))
    df["raw_row_id"] = df["raw_row_id"].astype("int64")
    return df


def sample_rows():
    """~40 representative rows: sales, cancellations, ledger lines, stock adjustments, zero prices, missing ids."""
    rows = []
    d = "2010-03-0{} 10:00:00"
    for i in range(1, 9):
        rows += [
            (f"50000{i}", "85048", "15CM CHRISTMAS GLASS BALL 20 LIGHTS", "12", d.format(i), "6.95", f"1300{i}.0", "United Kingdom"),
            (f"50000{i}", "79323p", " pink cherry lights ", "6", d.format(i), "6.75", f"1300{i}.0", "United Kingdom"),
            (f"50010{i}", "22041", "RECORD FRAME 7\" SINGLE SIZE", "4", d.format(i), "2.1", None, "France"),
        ]
    rows += [
        ("C500101", "85048", "15CM CHRISTMAS GLASS BALL 20 LIGHTS", "-2", "2010-03-09 11:00:00", "6.95", "13001.0", "United Kingdom"),   # legit return
        ("C500102", "22041", "RECORD FRAME 7\" SINGLE SIZE", "-1", "2010-03-09 11:05:00", "2.1", None, "France"),                           # legit, unidentified
        ("500201", "POST", "POSTAGE", "1", "2010-03-09 12:00:00", "18", "13002.0", "United Kingdom"),                                        # non-merchandise
        ("500202", "M", "Manual", "1", "2010-03-09 12:01:00", "9.5", None, "United Kingdom"),                                               # non-merchandise
        ("500203", "85048", "damaged", "-5", "2010-03-09 12:02:00", "0", None, "United Kingdom"),                                           # stock adjustment
        ("500204", "22041", None, "3", "2010-03-09 12:03:00", "0", None, "United Kingdom"),                                                  # zero price
        ("500205", "ZZZ", "Mystery", "1", "2010-03-09 12:04:00", "1.5", None, "United Kingdom"),                                             # unrecognised code
        ("500206", "TEST001", "This is a test product.", "1", "2010-03-09 12:05:00", "4.5", None, "United Kingdom"),                       # non-merchandise
    ]
    return rows


def run_stages(tmp_path, cfg, rows):
    """Run clean -> transform -> integrate on fixture rows (no Prefect). Returns ctx, summary, fact, tables, bronze, recon."""
    from retail_pipeline import integrate, privacy, transform, validation
    ctx = config.new_run(cfg, run_id="t", root=Path(tmp_path))
    bronze = bronze_from(rows)
    bp = Path(tmp_path) / "bronze.parquet"
    bronze.to_parquet(bp)
    summ = transform.build_silver(cfg, ctx, bp, privacy.load_secret(cfg))
    silver = Path(summ["silver_dir"])
    fact = transform.build_fact(cfg, ctx, silver)
    retained = pd.read_parquet(silver / "retained.parquet")
    tables = integrate.integrate(fact, retained)
    disp = pd.read_parquet(silver / "row_disposition.parquet")
    raw_rev = float((pd.to_numeric(bronze["Quantity"]) * pd.to_numeric(bronze["Price"])).sum())
    file_rows = {k: len(pd.read_parquet(silver / f"{k}.parquet")) for k in ("quarantine", "excluded")}
    recon = validation.build_reconciliation(cfg, raw_rows=len(bronze), raw_revenue_independent=raw_rev, disposition=disp,
                                            file_rows=file_rows, tables=tables, overlap_evidence=summ["overlap_evidence"])
    return ctx, summ, fact, tables, bronze, recon, file_rows, disp
