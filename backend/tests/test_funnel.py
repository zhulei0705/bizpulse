"""T06 漏斗测试：按企业计数（关键测试 2：5 次跟进仍算 1 家）、真实状态。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def _interaction(client, exp, target, **overrides):
    body = {
        "company_id": target["company_id"], "experiment_id": exp["id"], "target_id": target["id"],
        "occurred_at": "2026-10-02T10:00:00Z",
    }
    body.update(overrides)
    return client.post("/api/v1/interactions", json=body)


def test_funnel_counts_companies_not_interactions(client):
    """关键测试 2：一个企业发送 5 次跟进，Contacted Company 仍然只统计 1 家。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    for status in ["RESEARCHING", "READY_TO_CONTACT", "CONTACTED"]:
        client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status})
    for i in range(5):
        resp = _interaction(client, exp, target, interaction_type="FOLLOW_UP", direction="OUTBOUND", channel="EMAIL", subject=f"跟进 {i + 1}")
        assert resp.status_code == 200, resp.text

    funnel = client.get(f"/api/v1/experiments/{exp['id']}/funnel").json()["data"]
    assert funnel["targets"] == 1
    assert funnel["contacted"] == 1, "5 次互动仍是 1 家企业"
    assert funnel["replied"] == 0

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["contact_rate"] == 100.0
    assert metrics["reply_rate"] == 0


def test_funnel_zero_contacted_no_division_error(client):
    """关键测试 1：0 个已联系企业时 Reply Rate 不除零，统一返回 0。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    make_target(client, exp["id"], company["id"], with_opportunity=False)

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["contacted"] == 0
    assert metrics["reply_rate"] == 0
    assert metrics["meeting_rate"] == 0
    assert metrics["quote_rate"] == 0
    assert metrics["pilot_rate"] == 0
    assert metrics["close_rate"] == 0


def test_funnel_reflects_real_progression(client):
    exp = make_experiment(client, status="RUNNING")
    c1 = make_company(client)
    c2 = make_company(client)
    t1 = make_target(client, exp["id"], c1["id"], with_opportunity=False)
    t2 = make_target(client, exp["id"], c2["id"], with_opportunity=False)

    # 企业1：联系 → 回复 → 会议；企业2：只联系
    client.patch(f"/api/v1/experiment-targets/{t1['id']}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{t1['id']}", json={"status": "READY_TO_CONTACT"})
    client.patch(f"/api/v1/experiment-targets/{t1['id']}", json={"status": "CONTACTED"})
    client.patch(f"/api/v1/experiment-targets/{t2['id']}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{t2['id']}", json={"status": "READY_TO_CONTACT"})
    client.patch(f"/api/v1/experiment-targets/{t2['id']}", json={"status": "CONTACTED"})
    _interaction(client, exp, t1, interaction_type="REPLY", direction="INBOUND", channel="EMAIL", result="POSITIVE")
    _interaction(client, exp, t1, interaction_type="MEETING", direction="INBOUND", channel="MEETING")

    funnel = client.get(f"/api/v1/experiments/{exp['id']}/funnel").json()["data"]
    assert funnel["targets"] == 2
    assert funnel["contacted"] == 2
    assert funnel["replied"] == 1
    assert funnel["meetings"] == 1
    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["reply_rate"] == 50.0
    assert metrics["meeting_rate"] == 100.0


def test_funnel_reached_stage_survives_rollback(client):
    """状态回退后漏斗仍按到达过的最远阶段统计（真实到达过 = 进入过漏斗）。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    for status in ["RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED"]:
        client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status})
    # 回退到 READY_TO_CONTACT（比如联系错人，重新研究）
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "RESEARCHING"})

    funnel = client.get(f"/api/v1/experiments/{exp['id']}/funnel").json()["data"]
    row = funnel
    assert row["contacted"] == 1, "曾经联系过就计入已联系"
    assert row["replied"] == 1
