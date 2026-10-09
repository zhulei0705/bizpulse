"""T07 Experiment Snapshot 测试：开始实验时冻结假设/模型版本/报价假设。"""
from tests.helpers_t06 import make_experiment


def test_snapshot_created_on_start(client):
    exp = make_experiment(client, status="READY", price_amount=12800, price_currency="CNY")
    started = client.post(f"/api/v1/experiments/{exp['id']}/start").json()["data"]
    assert started["status"] == "RUNNING"

    detail = client.get(f"/api/v1/experiments/{exp['id']}").json()["data"]
    # ExperimentRead 不含 snapshot（对外聚合在 report）；直接查 report
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    snap = report["snapshot"]
    assert snap["market_hypothesis"] == exp["hypothesis"]
    assert snap["offer"]["price_amount"] == 12800
    assert snap["score_model_version"]
    assert snap["prompt_version"]
    assert snap["target_selection_rule"]


def test_snapshot_freezes_price_hypothesis_semantics(client):
    """报价在快照中标记为假设：客户真实接受前不得当作 validated_price。"""
    exp = make_experiment(client, status="READY", price_amount=9800, pricing_hypothesis="一次性验证服务 9800 元")
    client.post(f"/api/v1/experiments/{exp['id']}/start")
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    snap = report["snapshot"]
    assert snap["offer"]["pricing_hypothesis"] == "一次性验证服务 9800 元"


def test_report_separates_real_results_and_analysis(client):
    """报告必须区分【真实结果】与【系统分析】（任务书五十五）。"""
    exp = make_experiment(client, status="RUNNING")
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    assert "real_results" in report
    assert "system_analysis" in report
    assert "只读" in report["system_analysis"]["label"]
    assert report["real_results"]["metrics"]["targets"] == 0
    assert report["real_results"]["metrics"]["received_revenue"] == 0
