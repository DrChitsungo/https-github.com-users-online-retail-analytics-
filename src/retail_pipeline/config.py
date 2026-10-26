"""Configuration loading, run identity and code/rules fingerprints."""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("RETAIL_PIPELINE_HOME", Path(__file__).resolve().parents[2]))
CONFIG_PATH = ROOT / "configs" / "pipeline.yaml"


def load_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rules_hash(cfg: dict) -> str:
    """Hash of the full configuration; any rule change changes this value."""
    canonical = yaml.safe_dump(cfg, sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def code_hash() -> str:
    """Hash of all pipeline source files (a stand-in for a git commit when none exists)."""
    h = hashlib.sha256()
    for p in sorted((ROOT / "src" / "retail_pipeline").glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at: str
    root: Path
    rules_version: str
    rules_hash: str
    code_hash: str
    actor: str

    @property
    def run_dir(self) -> Path:
        return self.root / "data" / "runs" / self.run_id

    @property
    def report_dir(self) -> Path:
        return self.root / "reports" / "runs" / self.run_id


def new_run(cfg: dict, run_id: str | None = None, root: Path | None = None) -> RunContext:
    now = datetime.now(timezone.utc)
    rid = run_id or f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    actor = os.environ.get(cfg["privacy"]["service_actor_env_var"], cfg["privacy"]["default_actor"])
    return RunContext(
        run_id=rid,
        started_at=now.isoformat(timespec="seconds"),
        root=root or ROOT,
        rules_version=cfg["rules_version"],
        rules_hash=rules_hash(cfg),
        code_hash=code_hash(),
        actor=actor,
    )
