"""T07 Validation Brief 测试：【事实】【AI推断】【待验证】三分、真实证据、待验证问题。"""
from tests.helpers_t06 import make_approved_opportunity, make_company, make_experiment, make_target


def test_brief_statement_board_three_kinds(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])

    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    board = brief["statement_board"]
    kinds = {item["kind"] for item in board}
    assert "事实" in kinds, board
    assert "AI推断" in kinds
    assert "待验证" in kinds


def test_brief_facts_come_from_real_sources(client):
    """事实条目必须带真实来源 URL（不虚构）。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    fact_items = [x for x in brief["statement_board"] if x["kind"] == "事实"]
    assert fact_items, "应有来自真实来源的事实条目"
    assert any("http" in x["statement"] for x in fact_items)


def test_brief_includes_evidences_and_questions(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    assert brief["evidences"], "应包含机会关联的真实证据"
    assert brief["evidences"][0]["url"]
    assert brief["validation_questions"], "应包含验证问题（T05 生成）"
    assert brief["company"]["name"] == company["company_name"]
    assert brief["opportunity"]["score"] > 0


def test_brief_no_contact_is_honest(client):
    """没有真实联系人时如实说明，不生成猜测联系方式（任务书二十二/二十三）。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    assert brief["contacts"] == []
    assert "不得生成猜测" in brief["no_contact_note"]
