"""T06 互动记录测试：类型/方向真实性校验、收入规则、状态联动。"""
from tests.helpers_t06 import make_company, make_contact, make_experiment, make_target


def _post(client, **overrides):
    exp = overrides.pop("experiment")
    target = overrides.pop("target")
    body = {
        "company_id": target["company_id"],
        "experiment_id": exp["id"],
        "target_id": target["id"],
        "occurred_at": "2026-10-02T10:00:00Z",
    }
    body.update(overrides)
    return client.post("/api/v1/interactions", json=body)


def test_outreach_advances_target_and_opportunity(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    contact = make_contact(client, company["id"])

    resp = _post(client, experiment=exp, target=target, interaction_type="OUTREACH",
                 direction="OUTBOUND", channel="EMAIL", subject="首次触达", contact_id=contact["id"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["direction"] == "OUTBOUND"

    tid = target["id"]
    updated = client.get(f"/api/v1/experiments/{exp['id']}/targets").json()["data"]
    row = next(x for x in updated if x["id"] == tid)
    assert row["status"] == "CONTACTED"
    assert row["reached_stage"] == "CONTACTED"
    assert row["last_interaction_at"]

    # Opportunity 阶段同步推进 + 联系列数
    opp = client.get(f"/api/v1/opportunities/{target['opportunity_id']}").json()["data"]
    assert opp["stage"] == "CONTACTED"
    assert opp["contact_count"] == 1
    assert opp["last_contacted_at"]


def test_reply_must_be_inbound(client):
    """反伪造：客户回复必须 INBOUND。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    bad = _post(client, experiment=exp, target=target, interaction_type="REPLY", direction="OUTBOUND", channel="EMAIL")
    assert bad.status_code == 422
    assert "INBOUND" in bad.json()["detail"]


def test_revenue_only_on_contract_or_payment(client):
    """关键测试 3 前置：报价类型互动不允许记 revenue（报价不是收入）。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    bad = _post(client, experiment=exp, target=target, interaction_type="QUOTE", direction="OUTBOUND", revenue=5000)
    assert bad.status_code == 422
    assert "收入" in bad.json()["detail"]


def test_payment_records_revenue_and_wins(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    # 先推进到 QUOTED（真实流程）
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "READY_TO_CONTACT"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "CONTACTED"})
    resp = _post(client, experiment=exp, target=target, interaction_type="PAYMENT",
                 direction="INBOUND", revenue=9800, subject="客户付款")
    assert resp.status_code == 200, resp.text
    row = next(x for x in client.get(f"/api/v1/experiments/{exp['id']}/targets").json()["data"] if x["id"] == target["id"])
    assert row["status"] == "WON"
    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["wins"] == 1
    assert metrics["contracted_revenue"] == 9800


def test_reject_reason_only_on_rejection_type(client):
    """没有真实客户反馈不得编造拒绝原因。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    bad = _post(client, experiment=exp, target=target, interaction_type="NOTE",
                direction="INTERNAL", reject_reason="NO_BUDGET")
    assert bad.status_code == 422
    assert "拒绝原因" in bad.json()["detail"]


def test_interaction_list_filters_and_patch(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    created = _post(client, experiment=exp, target=target, interaction_type="RESEARCH", direction="INTERNAL").json()["data"]

    lst = client.get("/api/v1/interactions", params={"experiment_id": exp["id"]}).json()["data"]
    assert lst["total"] == 1

    patched = client.patch(f"/api/v1/interactions/{created['id']}", json={"summary": "查了官网与公开采购记录"})
    assert patched.status_code == 200
    assert patched.json()["data"]["summary"] == "查了官网与公开采购记录"


def test_unknown_interaction_type_rejected(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    resp = _post(client, experiment=exp, target=target, interaction_type="TELEPATHY", direction="OUTBOUND")
    assert resp.status_code == 422
