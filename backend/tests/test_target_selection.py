"""T07 目标选择测试：可解释 selection_reason、审核/证据门槛、去重与上限。"""
from tests.helpers_t06 import make_approved_opportunity, make_company, make_experiment


def test_select_by_opportunity_ids_with_reasons(client):
    exp = make_experiment(client, status="READY")
    company = make_company(client)
    opp = make_approved_opportunity(client, company["id"])

    resp = client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={"opportunity_ids": [opp["id"]]})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["selected_count"] == 1
    row = data["selected"][0]
    # 选择理由可解释（枚举+数值），不能只是"AI推荐"
    assert row["selection_reason"]
    assert any("MANUAL_PICK" not in r for r in row["selection_reason"]) or row["selection_reason"] == ["MANUAL_PICK(人工指定)"]
    assert row["company_name"] == company["company_name"]

    targets = client.get(f"/api/v1/experiments/{exp['id']}/targets").json()["data"]
    assert len(targets) == 1
    assert targets[0]["selection_reason"]


def test_select_skips_unapproved_and_duplicates(client):
    exp = make_experiment(client, status="READY")
    company = make_company(client)
    opp = make_approved_opportunity(client, company["id"])
    # 第一次选入
    client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={"opportunity_ids": [opp["id"]]})
    # 第二次选同一家 → skipped(already_in_experiment)
    resp = client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={"opportunity_ids": [opp["id"]]})
    data = resp.json()["data"]
    assert data["selected_count"] == 0
    assert data["skipped"][0]["reason"] == "already_in_experiment"


def test_select_respects_max_count(client):
    exp = make_experiment(client, status="READY")
    opps = []
    for _ in range(3):
        company = make_company(client)
        opps.append(make_approved_opportunity(client, company["id"]))
    resp = client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={
        "opportunity_ids": [o["id"] for o in opps], "max_count": 2,
    })
    data = resp.json()["data"]
    assert data["selected_count"] == 2


def test_select_high_intent_reason_recorded(client):
    """helpers 创建 intent=90 的机会 → 选择理由应包含 HIGH_INTENT 与具体分数。"""
    exp = make_experiment(client, status="READY")
    company = make_company(client)
    opp = make_approved_opportunity(client, company["id"])
    resp = client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={"opportunity_ids": [opp["id"]]})
    reasons = resp.json()["data"]["selected"][0]["selection_reason"]
    assert any(r.startswith("HIGH_INTENT") for r in reasons), reasons
    assert any(r.startswith("HIGH_SCORE") for r in reasons), reasons


def test_select_by_company_ids_picks_best_opportunity(client):
    exp = make_experiment(client, status="READY")
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    resp = client.post(f"/api/v1/experiments/{exp['id']}/targets/select", json={"company_ids": [company["id"]]})
    data = resp.json()["data"]
    assert data["selected_count"] == 1
    assert data["selected"][0]["opportunity_id"]
