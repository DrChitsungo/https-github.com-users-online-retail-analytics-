"""Immutable raw ingestion with provenance and checksums.

The raw CSV is never modified. Ingestion (1) verifies the pinned checksum, (2) reads every field as text
so parsing failures are measured rather than hidden, (3) writes a content-addressed 'bronze' Parquet copy
(all-text + raw_row_id) and (4) returns a provenance manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RunContext


class IngestionError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def ingest(cfg: dict, ctx: RunContext) -> dict:
    src = ctx.root / cfg["source"]["file"]
    if not src.exists():
        raise IngestionError(f"source file not found: {cfg['source']['file']} (see README 'Data acquisition')")
    sha = sha256_file(src)
    expected = cfg["source"].get("expected_sha256")
    if expected and sha != expected:
        raise IngestionError("source checksum does not match the pinned expected_sha256; refusing to ingest")

    try:  # immutability: drop write permission on the raw file (content is never modified)
        os.chmod(src, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except PermissionError:
        pass  # read-only mounts / non-owner: the checksum pin still detects any change

    df = pd.read_csv(src, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")
    if list(df.columns) != cfg["source"]["expected_columns"]:
        raise IngestionError("source columns differ from the expected schema")
    df.insert(0, "raw_row_id", np.arange(len(df), dtype="int64"))

    bronze_dir = ctx.root / "data" / "bronze" / sha[:12]
    bronze_dir.mkdir(parents=True, exist_ok=True)
    bronze = bronze_dir / "raw_strings.parquet"
    if bronze.exists():
        existing_rows = pd.read_parquet(bronze, columns=["raw_row_id"]).shape[0]
        if existing_rows != len(df):
            raise IngestionError("existing bronze copy disagrees with source; refusing to overwrite immutable data")
    else:
        df.to_parquet(bronze, index=False)
        os.chmod(bronze, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # read-only

    # independent revenue control total, computed straight from the raw text (not via cleaning.parse)
    raw_revenue = float((pd.to_numeric(df["Quantity"], errors="coerce") * pd.to_numeric(df["Price"], errors="coerce")).sum())

    manifest = {
        "run_id": ctx.run_id,
        "raw_revenue_control_total": round(raw_revenue, 4),
        "source_name": cfg["source"]["name"],
        "source_provider": cfg["source"]["provider"],
        "source_file": cfg["source"]["file"],
        "source_bytes": src.stat().st_size,
        "source_sha256": sha,
        "checksum_matches_pin": bool(expected and sha == expected),
        "rows": int(len(df)),
        "columns": cfg["source"]["expected_columns"],
        "bronze_path": str(bronze.relative_to(ctx.root)),
        "bronze_sha256": sha256_file(bronze),
        "actual_source_update_frequency": cfg["source"]["actual_update_frequency"],
        "rows_meets_minimum": bool(len(df) >= cfg["source"]["min_rows_required"]),
        "minimum_required": cfg["source"]["min_rows_required"],
    }
    ctx.report_dir.mkdir(parents=True, exist_ok=True)
    (ctx.report_dir / "ingestion_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
