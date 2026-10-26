"""End-to-end Prefect runs on a tiny hand-written fixture (not dataset data), using Prefect's test harness."""
import csv
import json
from pathlib import Path

import pytest
import yaml
from prefect.testing.utilities import prefect_test_harness

from conftest import RAW_COLS, ROOT, sample_rows
from retail_pipeline import config, flow
from retail_pipeline.validation import ValidationBlocked


@pytest.fixture(scope="module", autouse=True)
def harness():
    with prefect_test_harness():
        yield


def make_root(tmp_path, cfg, rows):
    (tmp_path / "data" / "raw").mkdir(parents=True)
    with open(tmp_path / "data" / "raw" / "online_retail_II.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(RAW_COLS); w.writerows([["" if v is None else v for v in r] for r in rows])
    cfgp = tmp_path / "pipeline.yaml"
    cfgp.write_text(yaml.safe_dump(cfg))
    return cfgp


def test_flow_declares_retries_only_on_io_and_none_on_publish():
    assert flow.t_ingest.retries == 2 and flow.t_publish.retries == 0


def test_successful_run_publishes_audits_and_is_deterministic(tmp_path, cfg):
    cfgp = make_root(tmp_path, cfg, sample_rows())
    out1 = flow.retail_pipeline(config_path=str(cfgp), run_id="it-1", root=str(tmp_path))
    out2 = flow.retail_pipeline(config_path=str(cfgp), run_id="it-2", root=str(tmp_path))
    assert out1["status"] == "SUCCEEDED" and out1["validation"]["outputs"]["critical_failures"] == 0
    m1 = json.loads((tmp_path / "data" / "published" / "it-1" / "MANIFEST.json").read_text())
    m2 = json.loads((tmp_path / "data" / "published" / "it-2" / "MANIFEST.json").read_text())
    assert {t: v["content_sha256"] for t, v in m1["tables"].items()} == {t: v["content_sha256"] for t, v in m2["tables"].items()}
    assert m1["build_id"] == m2["build_id"]
    import os
    import stat
    raw = tmp_path / "data" / "raw" / "online_retail_II.csv"
    assert not (raw.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))      # raw locked read-only
    bronze = next((tmp_path / "data" / "bronze").glob("*/raw_strings.parquet"))
    assert not (bronze.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))   # bronze locked read-only
    # audit log: all operation types present, no secret, no pseudonym
    log = (tmp_path / "reports" / "runs" / "it-1" / "audit_events.jsonl").read_text()
    ops = {json.loads(l)["operation"] for l in log.splitlines()}
    assert {"READ", "WRITE", "TRANSFORM", "VALIDATE", "PUBLISH", "RUN"} <= ops
    assert "unit-test-secret" not in log
    import pandas as pd
    keys = pd.read_parquet(tmp_path / "data" / "published" / "it-1" / "dim_customer.parquet")["customer_key"]
    assert not any(k in log for k in keys)


def test_critical_bronze_failure_blocks_run_and_publishes_nothing(tmp_path, cfg):
    bad = sample_rows() + [("500999", "85048", "X", "1", "2010-03-10 10:00:00", "abc", "13001.0", "United Kingdom")]
    cfgp = make_root(tmp_path, cfg, bad)
    with pytest.raises(ValidationBlocked):
        flow.retail_pipeline(config_path=str(cfgp), run_id="it-bad", root=str(tmp_path))
    st = json.loads((tmp_path / "reports" / "runs" / "it-bad" / "run_status.json").read_text())
    assert st["status"] == "FAILED" and st["published"] is False and "clean" in st["failed_tasks"]
    pub = tmp_path / "data" / "published"
    assert not pub.exists() or not any(pub.iterdir())


def test_missing_secret_fails_fast_before_any_processing(tmp_path, cfg, monkeypatch):
    cfgp = make_root(tmp_path, cfg, sample_rows())
    monkeypatch.delenv("CUSTOMER_KEY_SECRET")
    from retail_pipeline.privacy import SecretError
    with pytest.raises(SecretError):
        flow.retail_pipeline(config_path=str(cfgp), run_id="it-nosecret", root=str(tmp_path))
    assert not (tmp_path / "data" / "bronze").exists()


def test_checksum_pin_mismatch_is_refused(tmp_path, cfg):
    import copy
    c = copy.deepcopy(cfg); c["source"]["expected_sha256"] = "0" * 64
    cfgp = make_root(tmp_path, c, sample_rows())
    with pytest.raises(Exception) as e:
        flow.retail_pipeline(config_path=str(cfgp), run_id="it-pin", root=str(tmp_path))
    assert "IngestionError" in type(e.value).__name__ or "checksum" in str(e.value).lower()
    assert not (tmp_path / "data" / "published").exists()
