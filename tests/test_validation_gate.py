import json
from pathlib import Path

import great_expectations as gx
import pandas as pd
import pytest
from great_expectations import expectations as E

from conftest import run_stages, sample_rows
from retail_pipeline import publish, validation


@pytest.fixture()
def built(tmp_path, cfg):
    return run_stages(tmp_path, cfg, sample_rows())


def evaluate(cfg, built, tables):
    ctx, summ, fact, _, bronze, recon0, file_rows, disp = built
    raw_rev = float((pd.to_numeric(bronze["Quantity"]) * pd.to_numeric(bronze["Price"])).sum())
    recon = validation.build_reconciliation(cfg, raw_rows=len(bronze), raw_revenue_independent=raw_rev, disposition=disp,
                                            file_rows=file_rows, tables=tables, overlap_evidence=summ["overlap_evidence"])
    return validation.validate_outputs(cfg, tables, recon)


def failed(res):
    return {(s["suite"], i["expectation"], str(i["column"])) for s in res["suites"] for i in s["results"] if not i["success"] and i["severity"] == "critical"}


def test_clean_pipeline_output_passes_every_critical_check(cfg, built):
    res = evaluate(cfg, built, built[3])
    assert res["critical_failures"] == 0 and res["publish_allowed"]
    assert res["expectations_evaluated"] > 80 and all(r["within_tolerance"] for r in res["reconciliation"])


def test_legitimate_returns_and_cancellations_are_not_rejected(cfg, built):
    fact = built[2]
    returns = fact[fact["is_cancellation"] & (fact["quantity"] < 0)]
    assert len(returns) >= 2 and (returns["line_revenue"] < 0).all()
    assert evaluate(cfg, built, built[3])["publish_allowed"]


def _f(t, col, idx, value):
    t["fact_sales_line"].loc[idx, col] = value


def _dup_key(t):
    t["fact_sales_line"].loc[1, "line_id"] = t["fact_sales_line"].loc[0, "line_id"]


def _daily_dup(t):
    t["agg_daily_sales"] = pd.concat([t["agg_daily_sales"], t["agg_daily_sales"].iloc[[0]]], ignore_index=True)


def _leak_col(t):
    t["fact_sales_line"] = t["fact_sales_line"].assign(**{"Customer ID": 13001})


def _revenue(t):
    f = t["fact_sales_line"]
    f["line_revenue"] = f["line_revenue"] + 10


FAULTS = {
    "duplicate_primary_key": (_dup_key, "line_id"),
    "negative_price": (lambda t: _f(t, "unit_price", 2, -1.0), "unit_price"),
    "zero_quantity": (lambda t: _f(t, "quantity", 3, 0), "quantity"),
    "raw_id_instead_of_pseudonym": (lambda t: _f(t, "customer_key", 0, "13001"), "customer_key"),
    "cancellation_sign_mismatch": (lambda t: _f(t, "is_cancellation", 0, True), "chk_cancel_sign_consistent"),
    "orphan_stock_code": (lambda t: _f(t, "stock_code", 0, "99999"), "chk_stock_in_dim_product"),
    "revenue_no_longer_reconciles": (_revenue, "chk_revenue_formula"),
    "raw_customer_id_column_leaks_into_output": (_leak_col, "__schema"),
    "duplicate_daily_grain": (_daily_dup, "agg_daily_sales"),
    "email_in_product_description": (lambda t: t["dim_product"].loc.__setitem__((0, "description"), "contact a@b.com"), "description"),
}


@pytest.mark.parametrize("name", list(FAULTS))
def test_critical_faults_block_publication(cfg, built, name):
    mutate, marker = FAULTS[name]
    tables = {k: v.copy() for k, v in built[3].items()}
    mutate(tables)
    res = evaluate(cfg, built, tables)
    assert res["critical_failures"] >= 1 and not res["publish_allowed"], name
    assert any(marker in " ".join(f) for f in failed(res)), (name, failed(res))
    with pytest.raises(validation.ValidationBlocked):
        validation.assert_gate(res, "test")


def test_dropped_rows_break_row_count_reconciliation(cfg, built):
    tables = {k: v.copy() for k, v in built[3].items()}
    tables["fact_sales_line"] = tables["fact_sales_line"].iloc[:-3]
    res = evaluate(cfg, built, tables)
    assert not res["publish_allowed"] and any(not r["within_tolerance"] for r in res["reconciliation"])


def test_warning_failures_are_recorded_but_do_not_block():
    df = pd.DataFrame({"a": [1, None, 3, 4]})
    res = validation.run_suite(gx.get_context(mode="ephemeral"), "w", df, [E.ExpectColumnValuesToNotBeNull(column="a", severity="warning"),
                                                                           E.ExpectColumnValuesToNotBeNull(column="a", mostly=0.5, severity="critical")])
    assert res["warning_failures"] == 1 and res["critical_failures"] == 0


def test_saved_results_contain_no_unexpected_value_samples(cfg, built):
    text = json.dumps(evaluate(cfg, built, built[3]))
    assert "partial_unexpected" not in text and "unexpected_list" not in text


def _staging(tmp_path, tables):
    d = tmp_path / "stage"; d.mkdir()
    out = {}
    for k, v in tables.items():
        v.to_parquet(d / f"{k}.parquet", index=False); out[k] = d / f"{k}.parquet"
    return out


def test_publish_is_blocked_and_writes_nothing_when_a_gate_fails(cfg, built, tmp_path):
    ctx = built[0]
    res_bad = {"publish_allowed": False, "critical_failures": 3}
    ok_b = {"publish_allowed": True, "critical_failures": 0}
    with pytest.raises(publish.PublicationBlocked):
        publish.publish(ctx, cfg, _staging(tmp_path, built[3]), res_bad, ok_b, {"published_pii_hits": 0}, {"source_sha256": "abc"}, "kid")
    assert not (ctx.root / "data" / "published").exists() or not any((ctx.root / "data" / "published").iterdir())


def test_publish_blocked_by_pii_hit_even_when_validation_passes(cfg, built, tmp_path):
    ctx = built[0]
    ok = {"publish_allowed": True, "critical_failures": 0}
    with pytest.raises(publish.PublicationBlocked):
        publish.publish(ctx, cfg, _staging(tmp_path, built[3]), ok, ok, {"published_pii_hits": 2}, {"source_sha256": "abc"}, "kid")


def test_publish_succeeds_atomically_with_manifest_labelling_proposals(cfg, built, tmp_path):
    ctx = built[0]
    ok = {"publish_allowed": True, "critical_failures": 0}
    m = publish.publish(ctx, cfg, _staging(tmp_path, built[3]), ok, ok, {"published_pii_hits": 0}, {"source_sha256": "abc"}, "kid")
    pub = ctx.root / "data" / "published"
    assert (pub / ctx.run_id / "MANIFEST.json").exists() and json.loads((pub / "LATEST.json").read_text())["run_id"] == ctx.run_id
    assert not list(pub.glob(".tmp-*"))
    assert "PROPOSED" in m["refresh"]["status"] and "PROPOSED" in m["retention"]["status"]
    assert set(m["tables"]) == set(built[3])


def test_content_hash_is_deterministic_and_order_sensitive():
    a = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    assert publish.content_hash(a) == publish.content_hash(a.copy())
    assert publish.content_hash(a) != publish.content_hash(a.iloc[::-1].reset_index(drop=True))
