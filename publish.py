"""Publication gate and atomic publish. Nothing is written to the published zone unless every gate passes."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .catalog import CATALOG
from .config import RunContext
from .validation import ValidationBlocked


class PublicationBlocked(RuntimeError):
    """Raised when any publication gate fails."""


def content_hash(df: pd.DataFrame) -> str:
    """Deterministic hash of table CONTENT (independent of parquet file metadata)."""
    h = hashlib.sha256()
    h.update(("|".join(map(str, df.columns))).encode())
    h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
    return h.hexdigest()


def gates(validation: dict, privacy_result: dict, bronze_validation: dict) -> list[dict]:
    return [
        {"gate": "bronze critical expectations", "passed": bool(bronze_validation["publish_allowed"]),
         "detail": f"{bronze_validation['critical_failures']} critical failures"},
        {"gate": "output critical expectations + reconciliation", "passed": bool(validation["publish_allowed"]),
         "detail": f"{validation['critical_failures']} critical failures"},
        {"gate": "no PII patterns in published text", "passed": privacy_result["published_pii_hits"] == 0,
         "detail": f"{privacy_result['published_pii_hits']} hits"},
    ]


def publish(ctx: RunContext, cfg: dict, staging: dict[str, Path], validation: dict, bronze_validation: dict,
            privacy_result: dict, ingest_manifest: dict, key_id: str, audit=None) -> dict:
    g = gates(validation, privacy_result, bronze_validation)
    if not all(x["passed"] for x in g):
        if audit:
            audit.event("BLOCK", "published_zone", task="publish", outcome="blocked", gates_failed=sum(not x["passed"] for x in g))
        failed = [x["gate"] for x in g if not x["passed"]]
        raise PublicationBlocked(f"publication blocked by gate(s): {failed}")

    pub_root = ctx.root / "data" / "published"
    final = pub_root / ctx.run_id
    tmp = pub_root / f".tmp-{ctx.run_id}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    tables = {}
    for name, path in staging.items():
        df = pd.read_parquet(path)
        shutil.copy2(path, tmp / f"{name}.parquet")
        tables[name] = {
            "rows": int(len(df)), "columns": list(df.columns), "grain": CATALOG[name]["grain"],
            "primary_key": CATALOG[name]["primary_key"], "consumers": CATALOG[name]["consumers"],
            "sensitivity": CATALOG[name]["sensitivity"], "content_sha256": content_hash(df),
            "file_sha256": hashlib.sha256((tmp / f"{name}.parquet").read_bytes()).hexdigest(),
        }
        if audit:
            audit.event("WRITE", f"published/{name}", task="publish", rows_out=int(len(df)))
    build_id = hashlib.sha256("|".join([ingest_manifest["source_sha256"], ctx.rules_hash, ctx.code_hash, key_id]).encode()).hexdigest()[:16]
    manifest = {
        "run_id": ctx.run_id, "build_id": build_id,
        "published_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": ingest_manifest["source_sha256"], "rules_version": ctx.rules_version, "rules_hash": ctx.rules_hash,
        "code_hash": ctx.code_hash, "pseudonymisation_key_id": key_id,
        "gates": g, "tables": tables,
        "refresh": {
            "source_actual_update_frequency": cfg["source"]["actual_update_frequency"],
            "pipeline_proposed_schedule_cron": cfg["publish"]["proposed_schedule_cron"],
            "pipeline_proposed_schedule_note": cfg["publish"]["proposed_schedule_note"],
            "status": "PROPOSED - the pipeline has been run on demand only; no scheduler deployment was executed",
        },
        "retention": {"proposed_days": cfg["publish"]["proposed_retention_days"], "status": "PROPOSED policy, pending DPO agreement"},
    }
    (tmp / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    os.replace(tmp, final)  # atomic on the same filesystem
    (pub_root / "LATEST.json").write_text(json.dumps({"run_id": ctx.run_id, "build_id": build_id}, indent=2))
    if audit:
        audit.event("PUBLISH", "published_zone", task="publish", rows_out=sum(t["rows"] for t in tables.values()), tables=len(tables))
    return manifest
