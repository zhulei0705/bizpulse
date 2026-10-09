"""T08.0 P1-1 Experiment 一致性校验测试（任务书：target_company_count=1 vs target_contacts=30 冲突）。"""
from app.services.experiment_validation import validate_experiment_consistency
from tests.helpers_t06 import make_experiment


def test_target_count_mismatch_detected():
    """真实案例：target_company_count=1、target_contacts=30 → HIGH 冲突警告。"""
    experiment = type("E", (), {
        "target_company_count": 1, "target_contacts": 30,
        "success_criteria": "3 家目标企业中至少 1 家进入会议",
        "price_amount": 9800, "pricing_hypothesis": "试点 9800 元",
        "status": "DRAFT", "targets": [], "snapshot_json": {},
    })()
    warnings = validate_experiment_consistency(experiment)
    codes = {w["code"] for w in warnings}
    assert "TARGET_COUNT_MISMATCH" in codes
    assert "CRITERIA_EXCEEDS_TARGETS" in codes  # 成功标准 3 家 > 目标 1 家
    mismatch = next(w for w in warnings if w["code"] == "TARGET_COUNT_MISMATCH")
    assert mismatch["severity"] == "HIGH"


def test_consistent_experiment_no_high_warnings():
    experiment = type("E", (), {
        "target_company_count": 30, "target_contacts": 30,
        "success_criteria": "30 家目标企业回复率 >= 10%，至少 1 个付费试点",
        "price_amount": 9800, "pricing_hypothesis": "试点",
        "status": "DRAFT", "targets": [], "snapshot_json": {},
    })()
    warnings = validate_experiment_consistency(experiment)
    assert all(w["code"] not in {"TARGET_COUNT_MISMATCH", "CRITERIA_EXCEEDS_TARGETS"} for w in warnings)


def test_vague_criteria_and_missing_price_flagged():
    experiment = type("E", (), {
        "target_company_count": 10, "target_contacts": 10,
        "success_criteria": "", "price_amount": None, "pricing_hypothesis": None,
        "status": "DRAFT", "targets": [], "snapshot_json": {},
    })()
    codes = {w["code"] for w in validate_experiment_consistency(experiment)}
    assert "SUCCESS_CRITERIA_TOO_VAGUE" in codes
    assert "PRICE_HYPOTHESIS_MISSING" in codes


def test_start_api_returns_warnings(client):
    exp = make_experiment(client, status="READY")
    # 制造不一致
    client.patch(f"/api/v1/experiments/{exp['id']}", json={"target_contacts": 300})
    resp = client.post(f"/api/v1/experiments/{exp['id']}/start")
    assert resp.status_code == 200
    warnings = resp.json()["data"]["consistency_warnings"]
    assert any(w["code"] == "TARGET_COUNT_MISMATCH" for w in warnings)
