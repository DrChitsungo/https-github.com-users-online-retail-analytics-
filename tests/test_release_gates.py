"""Release gates (capstone Section 10): the committed evidence passes, and each gate blocks when its condition is broken."""
import copy, json
import pytest
from churn_model import release_gates as rg

CFG = rg._load("configs/release_gates.yaml")
if not (rg.ROOT / CFG["integrity"]["model_file"]).exists() or not (rg.ROOT / CFG["data_quality"]["run_summary"]).exists():
    pytest.skip("committed model/evidence files not present (e.g. inside the pipeline Docker image)", allow_module_level=True)


def test_committed_evidence_passes_all_automated_gates():
    res = rg.evaluate(CFG)
    assert res["automated_gates_passed"], res["gate_summary"]
    assert res["5_human_approval"]["required"] and res["5_human_approval"]["status"] == "PENDING"


@pytest.mark.parametrize("section,key,value,gate", [
    ("performance", "min_roc_auc", 0.90, "3_performance"),
    ("performance", "min_recall", 0.99, "3_performance"),
    ("fairness", "relative_band", [0.97, 1.03], "4_fairness"),
    ("fairness", "disparate_impact_band", [0.98, 1.02], "4_fairness"),
    ("fairness", "min_group_n", 1000, "4_fairness"),
    ("integrity", "required_horizon_days", 60, "2_integrity"),
    ("data_quality", "max_published_pii_hits", -1, "1_data_quality"),
])
def test_each_gate_blocks_when_threshold_not_met(section, key, value, gate):
    cfg = copy.deepcopy(CFG); cfg[section][key] = value
    res = rg.evaluate(cfg)
    assert not res["gate_summary"][gate] and not res["automated_gates_passed"]
    assert res["decision"].startswith("BLOCKED")


def test_tampered_model_file_fails_integrity(tmp_path, monkeypatch):
    fake = tmp_path / "model.joblib"; fake.write_bytes(b"not the champion")
    cfg = copy.deepcopy(CFG); cfg["integrity"]["model_file"] = str(fake)   # absolute path: ROOT / abs == abs
    res = rg.evaluate(cfg)
    assert not res["gate_summary"]["2_integrity"]


def test_cli_exit_codes(tmp_path):
    assert rg.main(["--out", str(tmp_path / "g.json")]) == 0
    bad = copy.deepcopy(CFG); bad["performance"]["min_roc_auc"] = 0.99
    p = tmp_path / "bad.yaml"; import yaml; p.write_text(yaml.safe_dump(bad))
    assert rg.main(["--config", str(p)]) == 1
    assert json.loads((tmp_path / "g.json").read_text())["automated_gates_passed"] is True
