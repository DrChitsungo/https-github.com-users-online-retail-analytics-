import numpy as np
import pandas as pd

from conftest import run_stages, sample_rows
from retail_pipeline import bias


def test_wilson_interval_known_values():
    lo, hi = bias.wilson(50, 100)
    assert abs(lo - 0.4038) < 1e-3 and abs(hi - 0.5962) < 1e-3
    assert all(np.isnan(x) for x in bias.wilson(0, 0))


def test_bias_report_structure_and_scope(tmp_path, cfg):
    ctx, summ, fact, tables, bronze, recon, file_rows, disp = run_stages(tmp_path, cfg, sample_rows())
    rep = bias.build_bias_report(cfg, disp, fact)
    assert rep["scope"]["protected_characteristics_available"] == []
    assert "no demographic fairness claim" in rep["scope"]["statement"].lower()
    for k in ["country_representation", "customer_identification_coverage", "cancellation_patterns", "time_coverage", "cleaning_impact", "findings", "mitigations", "limitations"]:
        assert k in rep
    shares = [r["share_lines"] for r in rep["country_representation"]["table"]]
    assert abs(sum(shares) - 1) < 0.01
    assert all(not r["evaluable"] for r in rep["cancellation_patterns"]["by_country"])   # tiny fixture: below min invoices
    assert not any(r["flag"] for r in rep["cancellation_patterns"]["by_country"])        # so nothing is flagged


def test_group_flagged_only_with_enough_data_and_ci_exclusion():
    inv = pd.DataFrame({"g": ["A"] * 400 + ["B"] * 400 + ["C"] * 20, "e": [1] * 40 + [0] * 360 + [1] * 160 + [0] * 240 + [1] * 20})
    overall = inv["e"].mean()
    rows = {r["group"]: r for r in bias._rate_table(inv, "g", "e", overall, [0.8, 1.25], 100)}
    assert rows["A"]["flag"] and rows["B"]["flag"]          # far below / far above overall, n >= 100
    assert not rows["C"]["evaluable"] and not rows["C"]["flag"]   # small group never flagged


def test_markdown_report_contains_limitations(tmp_path, cfg):
    ctx, summ, fact, tables, bronze, recon, file_rows, disp = run_stages(tmp_path, cfg, sample_rows())
    md = bias.to_markdown(bias.build_bias_report(cfg, disp, fact))
    assert "Limitations" in md and "internal representation imbalance" in md.lower()
