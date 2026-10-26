"""Render docs/data_dictionary.md and docs/lineage.md from docs/data_dictionary.yaml and the output catalog.
Usage: PYTHONPATH=src python scripts/build_docs.py"""
from pathlib import Path

import yaml

from retail_pipeline.catalog import CATALOG

root = Path(__file__).resolve().parents[1]
dd = yaml.safe_load((root / "docs" / "data_dictionary.yaml").read_text())

md = ["# Data Dictionary", "", "_Generated from `docs/data_dictionary.yaml`. Statistics marked (measured) describe the pinned source file._", "",
      "Sensitivity: S0 none, S1 internal business, S2 pseudonymous personal data (restricted), S3 raw identifier (restricted zone only).", "",
      f"## Source: {dd['source']['name']}", "", f"- Provider: {dd['source']['provider']}", f"- Format: {dd['source']['format']}",
      f"- Grain: {dd['source']['grain']}", f"- Actual update frequency of the source: {dd['source']['actual_update_frequency']}", "",
      "| Field | Source type | Target type | Nullable | Definition | Constraints / observed | Sensitivity |", "|---|---|---|---|---|---|---|"]
for f in dd["source"]["fields"]:
    md.append(f"| {f['name']} | {f['source_type']} | {f['target_type']} | {'yes' if f['nullable'] else 'no'} | {f['definition']} | {f['constraints']} {f['notes']} | {f['sensitivity']} |")
md += ["", "## Disposition and reason codes", "", dd["disposition_layout"]["description"], ""]
for c in dd["disposition_layout"]["columns"]:
    md.append(f"- `{c['name']}` ({c['type']}): {c['definition']}")
for name, t in dd["outputs"].items():
    cat = CATALOG[name]
    md += ["", f"## Output: `{name}`", "", t["description"], "", f"- Primary key: {', '.join(cat['primary_key'])}",
           f"- Consumers: {'; '.join(cat['consumers'])}", f"- Sensitivity note: {cat['sensitivity']}", "",
           "| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |", "|---|---|---|---|---|---|---|"]
    for c in t["columns"]:
        key = c.get("key", "") + (f" FK->{c['fk']}" if c.get("fk") else "")
        md.append(f"| {c['name']} | {c['type']} | {'yes' if c['nullable'] else 'no'} | {key.strip()} | {'yes' if c['derived'] else 'no'} | {c['definition']} | {c['sensitivity']} |")
(root / "docs" / "data_dictionary.md").write_text("\n".join(md) + "\n")

# lineage: raw field -> output columns
by_src: dict[str, list[str]] = {}
for tname, t in dd["outputs"].items():
    for c in t["columns"]:
        for s in c["lineage"]:
            by_src.setdefault(s, []).append(f"{tname}.{c['name']}")
lin = ["# Lineage", "", "```", "online_retail_II.csv (raw, immutable, read-only)", "  -> bronze/raw_strings.parquet        all-text copy + raw_row_id, content-addressed by sha256",
       "  -> silver/row_disposition|retained|quarantine|excluded.parquet   typed, rule-classified, Customer ID pseudonymised",
       "  -> silver/fact_sales_line.parquet     business transformations (line_revenue, is_cancellation, line_id)",
       "  -> staging/*.parquet                  dimensions, fact and aggregates",
       "  -> published/<run_id>/*.parquet       only after all validation + privacy gates pass", "```", "",
       "## Raw field to output field", "", "| Raw field | Output columns derived from it |", "|---|---|"]
for s in [f["name"] for f in dd["source"]["fields"]]:
    cols = by_src.get(s, [])
    lin.append(f"| {s} | {', '.join(cols[:14])}{' ...' if len(cols) > 14 else ''} ({len(cols)} columns) |")
lin += ["", "## Keys and grain", "", "| Table | Grain | Primary key | Foreign keys |", "|---|---|---|---|"]
for n, c in CATALOG.items():
    fks = "; ".join(f"{k} -> {v}" for k, v in c["foreign_keys"].items()) or "-"
    lin.append(f"| {n} | {c['grain']} | {', '.join(c['primary_key'])} | {fks} |")
lin += ["", "## Record disposition (what happens to each raw row)", "",
        "Every raw row receives exactly one of `retained`, `quarantined` or `excluded` with a reason code (see `cleaning.REASON_ORDER`). Raw rows = retained + quarantined + excluded is a critical reconciliation check on every run."]
(root / "docs" / "lineage.md").write_text("\n".join(lin) + "\n")
print("wrote docs/data_dictionary.md and docs/lineage.md")
