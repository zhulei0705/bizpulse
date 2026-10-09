"""T06 验证状态机综合测试：机会阶段保护 + Pain/Budget 确认闭环。"""
from tests.helpers_t06 import make_company, make_contact, make_experiment, make_target


def test_opportunity_stage_jump_blocked_and_force(client):
    exp = make_experiment(client)
    company = make_company(client)
    opp = make_opp_ready(client, company)
    # READY → MEETING 跳 2 步被拒
    resp = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "MEETING"})
    assert resp.status_code == 422
    # force + note 允许（人工确认真实事件）
    ok = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={
        "stage": "MEETING", "force": True, "note": "客户主动来电并当场约会议（真实事件）",
    })
    assert ok.status_code == 200
    assert ok.json()["data"]["stage"] == "MEETING"


def test_opportunity_won_requires_contract_amount(client):
    company = make_company(client)
    opp = make_opp_ready(client, company)
    client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "CONTACTED"})
    resp = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "WON"})
    assert resp.status_code == 422
    ok = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "WON", "contract_amount": 9800})
    assert ok.status_code == 200
    assert ok.json()["data"]["stage"] == "WON"


def test_opportunity_rejected_requires_reason(client):
    company = make_company(client)
    opp = make_opp_ready(client, company)
    client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "CONTACTED"})
    resp = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "REJECTED"})
    assert resp.status_code == 422
    ok = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={
        "stage": "REJECTED", "reject_reason": "NO_NEED",
    })
    assert ok.status_code == 200


def test_pain_confirm_requires_inbound_and_evidence(client):
    """T06↔T05 闭环：PainPoint INFERRED→CONFIRMED 只能来自真实客户沟通。"""
    from app.db.session import SessionLocal
    from app.models.pain_point import PainPoint

    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    make_contact(client, company["id"])

    # 造一个 INFERRED 痛点
    with SessionLocal() as db:
        pain = PainPoint(company_id=company["id"], category="SALES_EFFICIENCY", description="海外获客依赖人工", confidence=60, status="INFERRED")
        db.add(pain)
        db.commit()
        pain_id = pain.id

    # 内部笔记不能确认
    client.patch(f"/api/v1/opportunities/{target['opportunity_id']}/stage", json={"stage": "CONTACTED"})
    note = client.post("/api/v1/interactions", json={
        "company_id": company["id"], "experiment_id": exp["id"], "target_id": target["id"],
        "interaction_type": "NOTE", "direction": "INTERNAL", "summary": "内部猜测客户缺线索",
    })
    assert note.status_code == 200
    confirm_bad = client.post(f"/api/v1/interactions/{note.json()['data']['id']}/confirm-pain", json={"pain_point_id": pain_id})
    assert confirm_bad.status_code == 422

    # 客户真实回复（INBOUND + 原话）→ 可确认
    reply = client.post("/api/v1/interactions", json={
        "company_id": company["id"], "experiment_id": exp["id"], "target_id": target["id"],
        "interaction_type": "REPLY", "direction": "INBOUND", "channel": "EMAIL", "result": "POSITIVE",
        "summary": "客户回复：我们海外销售确实每天花3小时找线索，很痛。",
    })
    assert reply.status_code == 200
    confirm_ok = client.post(f"/api/v1/interactions/{reply.json()['data']['id']}/confirm-pain", json={
        "pain_point_id": pain_id, "note": "客户原话确认缺销售线索",
    })
    assert confirm_ok.status_code == 200, confirm_ok.text
    assert confirm_ok.json()["data"]["status"] == "CONFIRMED"

    with SessionLocal() as db:
        pain = db.get(PainPoint, pain_id)
        assert pain.status == "CONFIRMED"
        assert pain.confirmed_by_interaction_id == reply.json()["data"]["id"]


def test_budget_confirm_requires_customer_quote(client):
    """Budget 确认：客户明确说出预算才保存；必须引用 INBOUND 互动。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    client.patch(f"/api/v1/opportunities/{target['opportunity_id']}/stage", json={"stage": "CONTACTED"})

    # 无依据 → 422
    bad = client.post(f"/api/v1/opportunities/{target['opportunity_id']}/confirm-budget", json={"budget_text": "客户大概有5万预算"})
    assert bad.status_code == 422

    # 内部互动不能作为依据
    note = client.post("/api/v1/interactions", json={
        "company_id": company["id"], "experiment_id": exp["id"], "target_id": target["id"],
        "interaction_type": "NOTE", "direction": "INTERNAL", "summary": "内部猜测预算5万",
    })
    bad2 = client.post(f"/api/v1/opportunities/{target['opportunity_id']}/confirm-budget", json={
        "budget_text": "5万", "interaction_id": note.json()["data"]["id"],
    })
    assert bad2.status_code == 422

    # 客户来讯明确说预算 → 保存
    reply = client.post("/api/v1/interactions", json={
        "company_id": company["id"], "experiment_id": exp["id"], "target_id": target["id"],
        "interaction_type": "REPLY", "direction": "INBOUND", "channel": "WECHAT", "result": "NEED_MORE_INFO",
        "summary": "客户回复：预算5万元左右，要看到试点效果。",
    })
    ok = client.post(f"/api/v1/opportunities/{target['opportunity_id']}/confirm-budget", json={
        "budget_text": "预算5万元左右", "interaction_id": reply.json()["data"]["id"],
    })
    assert ok.status_code == 200
    assert ok.json()["data"]["confirmed_budget"] == "预算5万元左右"
    opp = client.get(f"/api/v1/opportunities/{target['opportunity_id']}").json()["data"]
    assert opp["confirmed_budget"] == "预算5万元左右"


def make_opp_ready(client, company):
    from tests.helpers_t06 import make_approved_opportunity
    return make_approved_opportunity(client, company["id"])
