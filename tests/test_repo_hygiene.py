import re
from pathlib import Path

from conftest import ROOT


def test_gitignore_blocks_data_secrets_and_run_artefacts():
    g = (ROOT / ".gitignore").read_text()
    for must in [".env", "data/", "reports/runs/", ".prefect/"]:
        assert must in g
    assert "!.env.example" in g


def test_env_example_contains_only_placeholders():
    t = (ROOT / ".env.example").read_text()
    assert "replace-with" in t
    assert not re.search(r"CUSTOMER_KEY_SECRET=[0-9a-f]{32,}", t)


def test_no_secret_like_values_or_raw_customer_ids_in_tracked_text_files():
    pat = re.compile(r"CUSTOMER_KEY_SECRET\s*=\s*(?!replace-with)\S{20,}")
    for p in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*")) + list((ROOT / "src").rglob("*.py")) + list((ROOT / "reports" / "latest").glob("*") if (ROOT / "reports" / "latest").exists() else []):
        if p.is_file() and p.suffix in {".md", ".py", ".yaml", ".json", ".jsonl", ".csv"} and "test" not in p.name:
            assert not pat.search(p.read_text(errors="ignore")), p


def test_dockerfile_pins_dependencies_and_does_not_bake_in_secrets():
    d = (ROOT / "Dockerfile").read_text()
    assert "requirements.lock.txt" in d and "CUSTOMER_KEY_SECRET" not in d and "USER pipeline" in d
    req = (ROOT / "requirements.txt").read_text()
    assert all("==" in l for l in req.splitlines() if l and not l.startswith("#"))
