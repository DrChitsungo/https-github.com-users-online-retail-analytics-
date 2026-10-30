"""Privacy controls: keyed pseudonymisation, free-text PII scrubbing, PII scanning, identifier inventory.

Accuracy note: HMAC-pseudonymised customer keys are PSEUDONYMOUS data, not anonymous data. Whoever holds
the secret (or the raw IDs) can re-link them, and combinations of country, timestamps and purchase
patterns can be quasi-identifying. Outputs must therefore stay inside the access boundary in
docs/governance.md.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

import pandas as pd


class SecretError(RuntimeError):
    """The pseudonymisation secret is missing or too weak. Raised WITHOUT echoing any value."""


def load_secret(cfg: dict) -> bytes:
    var = cfg["privacy"]["secret_env_var"]
    val = os.environ.get(var, "")
    if not val:
        raise SecretError(f"environment variable {var} is not set; see .env.example")
    if len(val) < cfg["privacy"]["min_secret_length"]:
        raise SecretError(f"{var} is shorter than the required {cfg['privacy']['min_secret_length']} characters")
    return val.encode("utf-8")


def key_id(secret: bytes) -> str:
    """Non-reversible label for WHICH key was used (supports rotation). Safe to log."""
    return hmac.new(secret, b"retail-pipeline-key-id", hashlib.sha256).hexdigest()[:8]


def pseudonymise_ids(ids: pd.Series, secret: bytes, hex_len: int = 32) -> pd.Series:
    """Keyed HMAC-SHA256 of the integer customer id, truncated. Nulls stay null. Deterministic per secret."""
    uniq = pd.Series(ids.dropna().unique())
    mapping = {
        int(v): hmac.new(secret, str(int(v)).encode(), hashlib.sha256).hexdigest()[:hex_len] for v in uniq
    }
    out = ids.map(lambda v: mapping.get(int(v)) if pd.notna(v) else None)
    return out.astype("string")


# ----- free-text scrubbing / scanning -------------------------------------------------------------
_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "url": re.compile(r"(?i)https?://|www\."),
    "phone_like": re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)"),
    "staff_name_after_by": re.compile(r"(?i)\b(?:adjustment|found|counted|checked|sorted|entered)\s+by\s+(?!the\b|dotcom\b)[a-z]+"),
}
_SCRUB_BY = re.compile(r"(?i)\b(adjustment|found|counted|checked|sorted|entered)\s+by\s+(?!the\b|dotcom\b)[a-z]+")


def scrub_text(s: pd.Series) -> pd.Series:
    """Trim/collapse whitespace and redact personal-name patterns from free text."""
    out = s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    out = out.str.replace(_PATTERNS["email"], "[EMAIL]", regex=True)
    out = out.str.replace(_PATTERNS["url"], "[URL]", regex=True)
    out = out.str.replace(_SCRUB_BY, r"\1 by [REDACTED]", regex=True)
    return out.replace("", pd.NA)


def pii_scan(df: pd.DataFrame, text_columns: list[str]) -> dict:
    """Count pattern hits per text column. Returns counts only, never matched text."""
    res: dict[str, dict[str, int]] = {}
    for col in text_columns:
        if col not in df.columns:
            continue
        s = df[col].dropna().astype("string")
        res[col] = {name: int(s.str.contains(p, regex=True).sum()) for name, p in _PATTERNS.items()}
    return res


def scan_total(scan: dict) -> int:
    return int(sum(v for col in scan.values() for v in col.values()))


def identifier_inventory(measured: dict) -> dict:
    """Classification of what the source does and does not contain. `measured` supplies counts."""
    return {
        "direct_identifiers": {
            "present": [],
            "absent": ["customer name", "postal address", "email address", "phone number", "payment card or bank details",
                       "date of birth", "government identifiers"],
            "note": "No direct identifiers were found in the eight source fields. Staff first names appear in a few "
                    "ledger-style free-text descriptions and are redacted on ingestion.",
            "measured_staff_name_pattern_rows_raw": measured.get("staff_name_rows_raw"),
        },
        "pseudonymous_identifiers": {
            "present": [{"field": "Customer ID", "treatment": "HMAC-SHA256 keyed pseudonym (customer_key); raw id never leaves the restricted bronze zone"}],
            "invoice_number": "Transaction identifier; retained because it is the transaction key. It does not identify a person on its own.",
        },
        "quasi_identifiers": {
            "present": ["Country", "InvoiceDate (to the second)", "purchase basket composition / purchase history per customer_key"],
            "risk": "Combined with outside knowledge these could single out a customer, especially in small countries.",
            "measured_countries_below_small_cell_threshold": measured.get("small_cell_countries"),
        },
        "sensitive_information": {
            "special_category_data": "Not present (no health, ethnicity, religion, biometric or similar fields).",
            "protected_characteristics": "Not present and NOT inferred. Demographic fairness cannot be assessed from this dataset.",
            "business_sensitive": ["unit prices", "revenue", "bank-charge / bad-debt ledger lines (excluded from published tables)"],
        },
    }
