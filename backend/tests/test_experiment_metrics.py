"""T06 转化指标测试：真实收入与报价分离（关键测试 3）、收入只来自成交。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def _interaction(client, exp, target, **overrides):
    body = {"company_id": target["company_id"], "experiment_id": exp["id"], "target_id": target["id"]}
    body.update(overrides)
    return client.post("/api/v1/interactions", json=body)


def _advance_to(client, target, *statuses):
    for status in statuses:
        resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status})
        assert resp.status_code == 200, resp.text


def test_contracted_vs_received_revenue_separated(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    _advance_to(client, target, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED", "QUALIFIED", "MEETING", "QUOTED", "PILOT")
    # 签约（合同金额 9800），收款 4900
    _interaction(client, exp, target, interaction_type="CONTRACT", direction="INTERNAL", revenue=9800, subject="签约")
    row = next(x for x in client.get(f"/api/v1/experiments/{exp['id']}/targets").json()["data"] if x["id"] == target["id"])
    assert row["status"] == "WON"
    _interaction(client, exp, target, interaction_type="PAYMENT", direction="INBOUND", revenue=4900, subject="首期款")

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["contracted_revenue"] == 9800
    assert metrics["received_revenue"] == 4900
    assert metrics["wins"] == 1


def test_metrics_rates_chain_correctly(client):
    exp = make_experiment(client, status="RUNNING")
    companies = [make_company(client) for _ in range(4)]
    targets = [make_target(client, exp["id"], c["id"], with_opportunity=False) for c in companies]
    # 4 家联系，2 家回复，1 家会议
    for t in targets:
        _advance_to(client, t, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED")
    _interaction(client, exp, targets[0], interaction_type="REPLY", direction="INBOUND", result="POSITIVE")
    _interaction(client, exp, targets[1], interaction_type="REPLY", direction="INBOUND", result="NEED_MORE_INFO")
    _interaction(client, exp, targets[0], interaction_type="MEETING", direction="INBOUND")

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["contact_rate"] == 100.0
    assert metrics["reply_rate"] == 50.0
    assert metrics["meeting_rate"] == 50.0
    assert metrics["quote_rate"] == 0
    assert metrics["pilots"] == 0


def test_no_interaction_no_fake_metrics(client):
    """七十七：正式库没有真实互动时保持 0，不为验收制造假互动。"""
    exp = make_experiment(client, status="RUNNING")
    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["targets"] == 0
    assert metrics["interaction_stats"]["interactions_total"] == 0
    assert metrics["contracted_revenue"] == 0
    assert metrics["received_revenue"] == 0
