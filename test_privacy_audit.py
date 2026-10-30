import json

import pandas as pd
import pytest

from retail_pipeline import config, privacy
from retail_pipeline.audit import AuditLogger, AuditViolation, read_events

S1, S2 = b"a" * 40, b"b" * 40


def test_pseudonymisation_is_deterministic_keyed_and_null_preserving():
    ids = pd.Series([13085, 13085, None, 12346], dtype="Int64")
    a, a2 = privacy.pseudonymise_ids(ids, S1), privacy.pseudonymise_ids(ids, S1)
    b = privacy.pseudonymise_ids(ids, S2)
    assert a.tolist()[:2] == a2.tolist()[:2] and a.iloc[0] == a.iloc[1]
    assert pd.isna(a.iloc[2]) and a.iloc[0] != a.iloc[3]
    assert a.iloc[0] != b.iloc[0]                       # different key -> different pseudonym
    assert all(len(v) == 32 and all(c in "0123456789abcdef" for c in v) for v in a.dropna())
    assert "13085" not in "".join(a.dropna())          # raw id not recoverable by inspection


def test_missing_or_weak_secret_fails_without_echoing_value(monkeypatch, cfg):
    monkeypatch.delenv("CUSTOMER_KEY_SECRET", raising=False)
    with pytest.raises(privacy.SecretError):
        privacy.load_secret(cfg)
    monkeypatch.setenv("CUSTOMER_KEY_SECRET", "short-secret-value")
    with pytest.raises(privacy.SecretError) as e:
        privacy.load_secret(cfg)
    assert "short-secret-value" not in str(e.value)


def test_key_id_does_not_reveal_secret():
    kid = privacy.key_id(S1)
    assert len(kid) == 8 and S1.decode() not in kid and kid != privacy.key_id(S2)


def test_pii_scan_returns_counts_only():
    df = pd.DataFrame({"d": ["mail me a@b.com", "visit www.x.com", "Adjustment by john on 1/1/2010", "PLAIN ITEM"]})
    scan = privacy.pii_scan(df, ["d"])
    assert scan["d"]["email"] == 1 and scan["d"]["url"] == 1 and scan["d"]["staff_name_after_by"] == 1
    assert all(isinstance(v, int) for v in scan["d"].values())


def test_inventory_states_what_is_absent_and_not_anonymous():
    inv = privacy.identifier_inventory({"staff_name_rows_raw": 71, "small_cell_countries": ["Bermuda"]})
    assert inv["direct_identifiers"]["present"] == []
    assert "NOT inferred" in inv["sensitive_information"]["protected_characteristics"]
    assert "pseudonym" in inv["pseudonymous_identifiers"]["present"][0]["treatment"].lower() or "HMAC" in inv["pseudonymous_identifiers"]["present"][0]["treatment"]


# ----------------------------------------------------------------------------- audit
@pytest.fixture()
def audit(tmp_path, cfg):
    ctx = config.new_run(cfg, run_id="audit-test", root=tmp_path)
    return AuditLogger(ctx, tmp_path / "audit.jsonl", forbidden_values=["TOP-SECRET-VALUE-0123456789"])


def test_audit_event_has_required_fields(audit):
    audit.event("READ", "raw/file.csv", task="ingest", rows_out=10)
    e = read_events(audit.path)[0]
    for k in ["run_id", "ts", "actor", "operation", "dataset", "rows_in", "rows_out", "outcome", "rules_version", "code_hash"]:
        assert k in e
    assert e["run_id"] == "audit-test" and e["operation"] == "READ" and e["rows_out"] == 10


def test_audit_refuses_secrets_identifiers_and_records(audit):
    with pytest.raises(AuditViolation):
        audit.event("READ", "x", note="TOP-SECRET-VALUE-0123456789")
    with pytest.raises(AuditViolation):
        audit.event("READ", "x", customer="13085.0")          # identifier-like
    with pytest.raises(AuditViolation):
        audit.event("READ", "x", row={"Customer ID": 1})        # structured record
    with pytest.raises(AuditViolation):
        audit.event("READ", "x", blob="y" * 500)                # too long to be metadata
    with pytest.raises(AuditViolation):
        audit.event("DELETE", "x")                              # unknown operation
    assert not audit.path.exists() or audit.path.read_text() == ""


def test_audit_span_logs_failure_with_class_only(audit):
    with pytest.raises(ValueError):
        with audit.span("TRANSFORM", "ds", task="t", rows_in=5):
            raise ValueError("message that could echo 13085 customer data")
    e = read_events(audit.path)[0]
    assert e["outcome"] == "failure" and e["detail"]["error_class"] == "ValueError"
    assert "13085" not in json.dumps(e)
