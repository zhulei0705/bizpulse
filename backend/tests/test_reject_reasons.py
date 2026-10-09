"""T06 拒绝原因测试（关键测试 4）：无回复不能记 NO_BUDGET；原因必须真实。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def _target_at(client, exp_id, company_id, *statuses):
    target = make_target(client, exp_id, company_id, with_opportunity=False)
    for status in statuses:
        resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status})
        assert resp.status_code == 200, resp.text
    return target


def test_reject_requires_reason(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = _target_at(client, exp["id"], company["id"], "RESEARCHING", "READY_TO_CONTACT")
    resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "REJECTED"})
    assert resp.status_code == 422
    assert "reject_reason" in resp.json()["detail"]


def test_reject_reason_must_be_enum(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = _target_at(client, exp["id"], company["id"], "RESEARCHING")
    resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "客户好像不太想要",
    })
    assert resp.status_code == 422
    assert "reject_reason 必须是" in resp.json()["detail"]


def test_no_budget_reason_requires_quote_stage(client):
    """没有真实价格沟通不能归因预算/价格：未到报价阶段不能记 NO_BUDGET/PRICE_HIGH。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = _target_at(client, exp["id"], company["id"], "RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED")
    resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "NO_BUDGET",
    })
    assert resp.status_code == 422
    assert "报价阶段" in resp.json()["detail"]

    # 到达报价阶段后，客户真实反馈价格问题 → 允许
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "QUALIFIED"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "MEETING"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "QUOTED"})
    ok = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "PRICE_HIGH", "notes": "客户回复：9800 超出今年预算",
    })
    assert ok.status_code == 200


def test_no_response_only_after_contacted(client):
    """没有回复就是 NO_RESPONSE；未联系过的目标不能标无回复。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    resp = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "NO_RESPONSE"})
    assert resp.status_code == 422
    assert "已联系" in resp.json()["detail"]

    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "READY_TO_CONTACT"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "CONTACTED"})
    ok = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "NO_RESPONSE"})
    assert ok.status_code == 200


def test_valid_reject_reasons_recorded_in_outcome(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = _target_at(client, exp["id"], company["id"], "RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED")
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "QUALIFIED"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "MEETING"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "QUOTED"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "ALREADY_HAVE_SOLUTION",
    })
    # Outcome 记录了拒绝原因分布的数据源
    from app.db.session import SessionLocal
    from app.models.experiment import ExperimentOutcome
    with SessionLocal() as db:
        outcome = db.query(ExperimentOutcome).filter(ExperimentOutcome.target_id == target["id"]).first()
        assert outcome is not None
        assert outcome.final_status == "REJECTED"
        assert outcome.reject_reason == "ALREADY_HAVE_SOLUTION"
        assert outcome.won is False
