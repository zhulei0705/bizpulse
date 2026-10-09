"""T06 实验生命周期测试：创建校验、状态管理、start/complete、结论枚举。"""
from tests.helpers_t06 import make_experiment, uniq


def test_create_experiment_with_full_definition(client):
    exp = make_experiment(client)
    assert exp["status"] == "READY"
    assert exp["hypothesis"]
    assert exp["value_proposition"]
    assert exp["price_amount"] == 9800
    assert exp["target_contacts"] == 30
    assert exp["success_criteria"]


def test_create_experiment_requires_hypothesis(client):
    resp = client.post("/api/v1/experiments", json={"name": f"空假设实验{uniq()}", "hypothesis": ""})
    assert resp.status_code == 422


def test_experiment_invalid_status_rejected(client):
    resp = client.post("/api/v1/experiments", json={"name": f"坏状态{uniq()}", "hypothesis": "x", "status": "RUNNING_FOREVER"})
    assert resp.status_code == 422


def test_experiment_lifecycle_start_complete(client):
    exp = make_experiment(client, status="DRAFT")
    started = client.post(f"/api/v1/experiments/{exp['id']}/start")
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "RUNNING"
    assert started.json()["data"]["started_at"]

    # 结论必须是枚举（V1 人工判断）
    bad = client.post(f"/api/v1/experiments/{exp['id']}/complete", json={"conclusion": "AUTO_AI_DECIDED"})
    assert bad.status_code == 422
    completed = client.post(f"/api/v1/experiments/{exp['id']}/complete", json={"conclusion": "TEST_MORE", "notes": "回复率未达标，扩大样本"})
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "COMPLETED"
    assert completed.json()["data"]["conclusion"] == "TEST_MORE"

    # 重复完成 → 409
    again = client.post(f"/api/v1/experiments/{exp['id']}/complete", json={})
    assert again.status_code == 409


def test_experiment_detail_includes_real_metrics(client):
    exp = make_experiment(client)
    detail = client.get(f"/api/v1/experiments/{exp['id']}").json()["data"]
    assert {"metrics", "funnel", "interaction_stats"} <= set(detail.keys())
    # 没有任何真实互动时全部为 0（REAL_DATA_ONLY：没有发生就显示 0）
    assert detail["metrics"]["targets"] == 0
    assert detail["metrics"]["contracted_revenue"] == 0
