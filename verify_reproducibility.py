"""Compare two completed runs table-by-table (content hashes) to evidence deterministic processing.
Usage: python scripts/verify_reproducibility.py run-001 run-002 reports/evidence/reproducibility_check.json
Runs must use the same raw data, config, code and CUSTOMER_KEY_SECRET (same pseudonymisation key_id)."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
a, b, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
ma = json.loads((root / "data" / "published" / a / "MANIFEST.json").read_text())
mb = json.loads((root / "data" / "published" / b / "MANIFEST.json").read_text())
rows = []
for t in ma["tables"]:
    rows.append({"table": t, "rows_a": ma["tables"][t]["rows"], "rows_b": mb["tables"][t]["rows"],
                 "content_identical": ma["tables"][t]["content_sha256"] == mb["tables"][t]["content_sha256"],
                 "file_bytes_identical": ma["tables"][t]["file_sha256"] == mb["tables"][t]["file_sha256"]})
res = {"run_a": a, "run_b": b, "same_build_id": ma["build_id"] == mb["build_id"], "build_id": ma["build_id"],
       "same_key_id": ma["pseudonymisation_key_id"] == mb["pseudonymisation_key_id"], "tables": rows,
       "all_content_identical": all(r["content_identical"] for r in rows)}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(res, indent=2))
print(json.dumps({k: v for k, v in res.items() if k != "tables"}, indent=2), *[f"{r['table']}: content {r['content_identical']} file {r['file_bytes_identical']}" for r in rows], sep="\n")
assert res["all_content_identical"] and res["same_build_id"]
