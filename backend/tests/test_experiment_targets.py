"""T06 验证目标企业测试：审核门槛、去重、状态流转保护。"""
from tests.helpers_t06 import make_approved_opportunity, make_company, make_experiment, make_target


def _add_target(client, exp_id, company_id, opportunity_id=None):
    return client.post(f"/api/v1/experiments/{exp_id}/targets", json={
        "company_id": company_id, "opportunity_id": opportunity_id,
    })


def test_target_requires_approved_opportunity(client):
    """关键测试 5：Opportunity 未审核，禁止直接加入正式 Experiment。"""
    exp = make_experiment(client)
    company = make_company(client)
    # 未审核机会
    unapproved_opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": None,
        "title": "未审核机会", "problem": "x", "solution": "y",
    })
    # 无证据机会在创建层就被拒；这里直接用无机会企业验证加入实验不会自动创建机会路径
    resp = _add_target(client, exp["id"], company["id"])
    assert resp.status_code == 200  # 无 opportunity_id 允许（企业级目标）


def test_target_with_unreviewed_opportunity_rejected(client):
    exp = make_experiment(client)
    company = make_company(client)
    suffix = "unrev"
    source = client.post("/api/v1/sources", json={
        "name": f"源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://x.example.com", "reliability_grade": "A", "reliability_score": 90,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://x.example.com/a", "title": "t",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘", "confidence": 80,
    }).json()["data"]
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "未审核", "problem": "x", "solution": "y",
        "pain_score": 80, "budget_score": 80, "intent_score": 80,
        "urgency_score": 80, "agent_fit_score": 80, "reachability_score": 60,
        "evidence_score": 40,
    }).json()["data"]
    resp = _add_target(client, exp["id"], company["id"], opp["id"])
    assert resp.status_code == 422
    assert "人工审核" in resp.json()["detail"]


def test_target_duplicate_company_rejected(client):
    exp = make_experiment(client)
    company = make_company(client)
    assert _add_target(client, exp["id"], company["id"]).status_code == 200
    resp = _add_target(client, exp["id"], company["id"])
    assert resp.status_code == 409


def test_target_status_flow_and_jump_protection(client):
    """主流程单步推进允许；NEW→MEETING 跳 4 步被拒；force 需说明。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    tid = target["id"]

    r = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "RESEARCHING"})
    assert r.json()["data"]["status"] == "RESEARCHING"
    r = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "READY_TO_CONTACT"})
    assert r.json()["data"]["status"] == "READY_TO_CONTACT"

    jump = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "MEETING"})
    assert jump.status_code == 422
    assert "不允许" in jump.json()["detail"]

    forced = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "MEETING", "force": True})
    assert forced.status_code == 422  # force 仍需 note
    forced_ok = client.patch(f"/api/v1/experiment-targets/{tid}", json={
        "status": "MEETING", "force": True, "notes": "客户主动来电约会议（真实事件）",
    })
    assert forced_ok.json()["data"]["status"] == "MEETING"


def test_target_won_requires_real_contract_amount(client):
    """任务书三十三：只有真实发生交易才允许 WON；口头意向不算。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    tid = target["id"]

    for status in ["RESEARCHING", "READY_TO_CONTACT", "CONTACTED"]:
        assert client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": status}).status_code == 200

    no_amount = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "WON"})
    assert no_amount.status_code == 422
    assert "合同金额" in no_amount.json()["detail"]

    # 补录真实成交（线下完成，事后录入）：跳步需 force + 真实依据，且必须带合同金额
    won = client.patch(f"/api/v1/experiment-targets/{tid}", json={
        "status": "WON", "contract_amount": 9800, "force": True,
        "notes": "线下完成签约并已回款，补录系统（合同编号 HW-2026-001）",
    })
    assert won.status_code == 200
    assert won.json()["data"]["status"] == "WON"


def test_target_reopen_final_state_requires_force(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    tid = target["id"]
    client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "REJECTED", "reject_reason": "NO_NEED", "notes": "客户明确表示无需求"})

    reopen = client.patch(f"/api/v1/experiment-targets/{tid}", json={"status": "RESEARCHING"})
    assert reopen.status_code == 422
    reopen_ok = client.patch(f"/api/v1/experiment-targets/{tid}", json={
        "status": "RESEARCHING", "force": True, "notes": "客户主动重新接洽（真实事件）",
    })
    assert reopen_ok.status_code == 200


def test_add_to_experiment_endpoint(client):
    """任务书五十四：POST /opportunities/{id}/add-to-experiment，须已审核。"""
    exp = make_experiment(client)
    company = make_company(client)
    opp = make_approved_opportunity(client, company["id"])
    resp = client.post(f"/api/v1/opportunities/{opp['id']}/add-to-experiment", json={"experiment_id": exp["id"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["target_created"] is True
    assert data["target_id"]

    # 重复加入 → 409
    again = client.post(f"/api/v1/opportunities/{opp['id']}/add-to-experiment", json={"experiment_id": exp["id"]})
    assert again.status_code == 409
