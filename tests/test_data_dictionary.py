from pathlib import Path

import yaml

from conftest import ROOT, run_stages, sample_rows
from retail_pipeline import validation
from retail_pipeline.catalog import CATALOG

DD = yaml.safe_load((ROOT / "docs" / "data_dictionary.yaml").read_text())


def test_dictionary_covers_every_output_table_and_matches_catalog():
    assert set(DD["outputs"]) == set(CATALOG) == set(validation.OUTPUT_SCHEMAS)


def test_dictionary_columns_match_validation_schema_and_real_output(tmp_path, cfg):
    tables = run_stages(tmp_path, cfg, sample_rows())[3]
    for name, spec in DD["outputs"].items():
        cols = [c["name"] for c in spec["columns"]]
        assert cols == validation.OUTPUT_SCHEMAS[name] == list(tables[name].columns), name


def test_every_column_is_fully_documented_and_keys_are_not_nullable():
    for name, spec in DD["outputs"].items():
        pk = set(CATALOG[name]["primary_key"])
        for c in spec["columns"]:
            assert c["definition"] and c["type"] and c["sensitivity"] in {"S0", "S1", "S2", "S3"} and "nullable" in c and "lineage" in c, (name, c["name"])
            if c["name"] in pk:
                assert c["nullable"] is False
    assert {c["name"] for t in DD["outputs"].values() for c in t["columns"] if "customer" in c["name"].lower() and c["name"].endswith("key")}


def test_source_fields_match_config_and_raw_identifier_is_s3():
    from retail_pipeline import config
    names = [f["name"] for f in DD["source"]["fields"]]
    assert names == config.load_config()["source"]["expected_columns"]
    by = {f["name"]: f for f in DD["source"]["fields"]}
    assert by["Customer ID"]["sensitivity"] == "S3" and by["Customer ID"]["nullable"] is True
    assert all(f["definition"] and f["constraints"] is not None for f in DD["source"]["fields"])


def test_no_output_column_exposes_the_raw_customer_id():
    for spec in DD["outputs"].values():
        for c in spec["columns"]:
            assert c["name"].lower() not in {"customer id", "customer_id"}
            if c["name"] == "customer_key":
                assert c["sensitivity"] == "S2"


def test_generated_markdown_is_in_sync():
    md = (ROOT / "docs" / "data_dictionary.md").read_text()
    for t, spec in DD["outputs"].items():
        assert f"## Output: `{t}`" in md and all(f"| {c['name']} |" in md for c in spec["columns"])
