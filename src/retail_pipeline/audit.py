"""Structured privacy audit log for every pipeline-managed read, write and transformation.

Design rules (enforced in code and tested):
  * events carry metadata only: run id, timestamp, actor, operation, dataset, row counts, outcome,
    rule/code version. Never raw records, customer identifiers or secrets.
  * `detail` accepts only short scalars and refuses values that look like identifiers or secrets.
  * This log covers access made THROUGH the pipeline. Reads of the files by people or other tools
    require storage/platform audit controls (e.g. Azure Storage diagnostic logs); see docs/governance.md.
"""
from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import RunContext

OPERATIONS = {"READ", "WRITE", "TRANSFORM", "VALIDATE", "PUBLISH", "BLOCK", "RUN"}
_ALLOWED_DETAIL_TYPES = (int, float, bool, str, type(None))
_ID_LIKE = re.compile(r"\b\d{5}(?:\.0)?\b")  # five-digit numbers resemble Customer IDs


class AuditViolation(ValueError):
    """Raised when an audit event would contain something that must not be logged."""


class AuditLogger:
    def __init__(self, ctx: RunContext, path: Path, forbidden_values: list[str] | None = None):
        self.ctx = ctx
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seq = 0
        self._forbidden = [v for v in (forbidden_values or []) if v]

    def _check_detail(self, detail: dict) -> dict:
        clean = {}
        for k, v in detail.items():
            if not isinstance(v, _ALLOWED_DETAIL_TYPES):
                raise AuditViolation(f"detail '{k}' has non-scalar type {type(v).__name__}")
            if isinstance(v, str):
                if len(v) > 160:
                    raise AuditViolation(f"detail '{k}' too long to be metadata")
                if any(f in v for f in self._forbidden):
                    raise AuditViolation(f"detail '{k}' contains a forbidden value")
                if _ID_LIKE.search(v):
                    raise AuditViolation(f"detail '{k}' looks like an identifier")
            clean[k] = v
        return clean

    def event(self, operation: str, dataset: str, *, task: str = "", rows_in: int | None = None,
              rows_out: int | None = None, outcome: str = "success", **detail) -> dict:
        if operation not in OPERATIONS:
            raise AuditViolation(f"unknown operation {operation}")
        with self._lock:
            self._seq += 1
            rec = {
                "seq": self._seq,
                "run_id": self.ctx.run_id,
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "actor": self.ctx.actor,
                "operation": operation,
                "task": task,
                "dataset": dataset,
                "rows_in": rows_in,
                "rows_out": rows_out,
                "outcome": outcome,
                "rules_version": self.ctx.rules_version,
                "rules_hash": self.ctx.rules_hash,
                "code_hash": self.ctx.code_hash,
                "detail": self._check_detail(detail),
            }
            line = json.dumps(rec, sort_keys=True)
            if any(f in line for f in self._forbidden):
                raise AuditViolation("event contains a forbidden value")
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return rec

    @contextmanager
    def span(self, operation: str, dataset: str, *, task: str = "", rows_in: int | None = None, **detail):
        """Log one event whose outcome/row count are set by the caller via the yielded dict."""
        state = {"rows_out": None, "extra": {}}
        try:
            yield state
        except Exception as exc:  # log the exception CLASS only; messages may echo data
            self.event(operation, dataset, task=task, rows_in=rows_in, rows_out=state["rows_out"],
                       outcome="failure", error_class=type(exc).__name__, **detail)
            raise
        else:
            self.event(operation, dataset, task=task, rows_in=rows_in, rows_out=state["rows_out"],
                       outcome="success", **{**detail, **state["extra"]})


def read_events(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
