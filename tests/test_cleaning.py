import copy

import pandas as pd

from conftest import bronze_from, sample_rows
from retail_pipeline import cleaning


def classify(rows, cfg):
    b = bronze_from(rows)
    p = cleaning.parse(b, cfg)
    block, dup, ev = cleaning.detect_overlap(b, p, cfg)
    return b, p, cleaning.classify(p, b, dup, cfg), block, dup, ev


def row(inv="500001", sc="85048", desc="SOME ITEM", qty="1", ts="2010-03-01 10:00:00", price="2.5", cust="13001.0", ctry="United Kingdom"):
    return (inv, sc, desc, qty, ts, price, cust, ctry)


def reason(rows, cfg):
    return classify(rows, cfg)[2]["reason_code"].tolist()


def test_legitimate_return_is_retained_not_rejected(cfg):
    assert reason([row(inv="C500001", qty="-3")], cfg) == ["OK"]


def test_negative_quantity_on_sale_invoice_is_stock_adjustment(cfg):
    assert reason([row(qty="-5", price="0")], cfg) == ["QRN_STOCK_ADJUSTMENT"]


def test_cancellation_with_positive_quantity_quarantined(cfg):
    assert reason([row(inv="C500001", qty="2")], cfg) == ["QRN_CANCEL_POSITIVE_QTY"]


def test_zero_and_negative_price_quarantined(cfg):
    assert reason([row(price="0"), row(price="-3")], cfg) == ["QRN_ZERO_PRICE", "QRN_NEGATIVE_PRICE"]


def test_non_merchandise_codes_excluded(cfg):
    codes = ["POST", "M", "BANK CHARGES", "TEST001", "GIFT_0001_20", "adjust2", "AMAZONFEE", "DOT"]
    assert set(reason([row(sc=c) for c in codes], cfg)) == {"EXC_NON_MERCHANDISE"}


def test_unrecognised_stock_code_quarantined(cfg):
    assert reason([row(sc="ZZZ")], cfg) == ["QRN_UNRECOGNISED_STOCKCODE"]


def test_missing_description_on_priced_line_quarantined(cfg):
    assert reason([row(desc=None)], cfg) == ["QRN_MISSING_DESCRIPTION"]


def test_parse_failures_are_flagged_not_raised(cfg):
    rows = [row(price="abc"), row(qty="1.5"), row(ts="not a date"), row(cust="12ab")]
    assert reason(rows, cfg) == ["QRN_PARSE_FAILURE"] * 4


def test_missing_customer_id_is_retained_as_unidentified(cfg):
    b, p, d, *_ = classify([row(cust=None)], cfg)
    assert d["disposition"].iloc[0] == "retained" and p["customer_id_raw"].isna().iloc[0]


def test_stock_code_case_and_whitespace_normalised(cfg):
    b = bronze_from([row(sc=" 79323p ")])
    assert cleaning.parse(b, cfg)["stock_code"].iloc[0] == "79323P"


def test_staff_name_redacted_in_free_text(cfg):
    b = bronze_from([row(sc="ADJUST", desc="Adjustment by john on 26/01/2010 16"), row(desc="sold as set by dotcom")])
    p = cleaning.parse(b, cfg)
    assert "john" not in p["description"].iloc[0].lower() and "[REDACTED]" in p["description"].iloc[0]
    assert p["description"].iloc[1] == "sold as set by dotcom"


def test_every_row_gets_exactly_one_disposition_and_counts_partition(cfg):
    b, p, d, *_ = classify(sample_rows(), cfg)
    assert len(d) == len(b)
    assert set(d["disposition"]) <= {"retained", "quarantined", "excluded"}
    assert d["disposition"].value_counts().sum() == len(b)
    assert (d["reason_code"] == "OK").sum() == (d["disposition"] == "retained").sum()


def test_within_source_exact_duplicates_retained_and_flagged_by_default(cfg):
    rows = [row(), row(), row(inv="500002")]
    _, _, d, *_ = classify(rows, cfg)
    assert d["disposition"].tolist() == ["retained"] * 3
    assert d["is_exact_duplicate_within_source"].tolist() == [False, True, False]


def test_within_source_duplicates_dropped_only_when_configured(cfg):
    c = copy.deepcopy(cfg)
    c["rules"]["drop_within_source_exact_duplicates"] = True
    _, _, d, *_ = classify([row(), row()], c)
    assert d["reason_code"].tolist() == ["OK", "EXC_DUP_WITHIN_SOURCE"]


# ---------------------------------------------------------------- overlap between source blocks
def _ov(inv, ts, qty="1"):
    return row(inv=inv, ts=ts, qty=qty, cust=None)


def _two_blocks(block2_override=None):
    block1 = [_ov("500001", "2010-11-30 09:00:00"), _ov("500002", "2010-12-01 09:00:00"), _ov("500003", "2010-12-05 09:00:00"), _ov("500004", "2010-12-09 09:00:00")]
    block2 = [_ov("500002", "2010-12-01 09:00:00"), _ov("500003", "2010-12-05 09:00:00"), _ov("500004", "2010-12-09 09:00:00"),
              _ov("500005", "2010-12-10 09:00:00"), _ov("500006", "2010-12-11 09:00:00")]
    if block2_override:
        block2 = block2_override(block2)
    return block1 + block2


def test_overlap_excluded_when_records_verified_identical(cfg):
    _, _, d, block, dup, ev = classify(_two_blocks(), cfg)
    assert ev["verified"] and ev["rows_block1_in_window"] == ev["rows_block2_in_window"] == 3
    assert dup.tolist() == [False] * 4 + [True] * 3 + [False] * 2
    assert block.tolist() == [1] * 4 + [2] * 5
    assert d["reason_code"].tolist().count("EXC_DUP_OVERLAP") == 3


def test_overlap_not_excluded_when_records_differ(cfg):
    rows = _two_blocks(lambda b: [b[0][:3] + ("99",) + b[0][4:]] + b[1:])  # quantity differs on one record
    _, _, d, _, dup, ev = classify(rows, cfg)
    assert not ev["verified"] and dup.sum() == 0
    assert "EXC_DUP_OVERLAP" not in d["reason_code"].tolist()


def test_chronological_reset_alone_does_not_remove_records(cfg):
    # a date reset with DIFFERENT invoices in the window must not be treated as duplicates
    rows = [_ov("500001", "2010-12-05 09:00:00"), _ov("500002", "2010-12-09 09:00:00"), _ov("600001", "2010-12-01 09:00:00"), _ov("600002", "2010-12-06 09:00:00")]
    _, _, d, _, dup, ev = classify(rows, cfg)
    assert dup.sum() == 0 and not ev["verified"]


def test_no_backward_step_means_no_overlap_handling(cfg):
    rows = [_ov("500001", "2010-12-01 09:00:00"), _ov("500002", "2010-12-02 09:00:00")]
    _, _, d, _, dup, ev = classify(rows, cfg)
    assert dup.sum() == 0 and ev["backward_steps_in_file_order"] == 0
