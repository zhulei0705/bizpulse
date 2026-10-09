"""T07 Outreach Package 测试：草稿只引用真实信号、禁止虚假个性化、不自动发送。"""
from tests.helpers_t06 import make_approved_opportunity, make_company, make_experiment, make_target


def test_draft_is_draft_only(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    draft = brief["outreach_draft"]
    assert draft["is_draft_only"] is True
    assert draft["warning"]
    assert "不推销" in draft["body"] or "调研" in draft["body"]


def test_draft_references_real_signal_not_fabricated(client):
    """草稿必须引用真实公开信号（事实条目），不得出现虚假个性化数字。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    body = brief["outreach_draft"]["body"]
    # 引用了事实条目（含真实来源 URL 或企业名）
    assert company["company_name"] in body
    # 禁止虚构个性化：不得出现"营收增长/融资"等无依据表述
    for banned in ["营收增长", "最近融资", "毛利率提升"]:
        assert banned not in body, f"草稿出现未证实的个性化表述：{banned}"


def test_draft_mentions_low_barrier_next_step(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    body = brief["outreach_draft"]["body"]
    assert "15~30 分钟" in body


def test_package_structure_complete(client):
    """Outreach Package 六要素：Company Brief / Evidence / Contact / Draft / Questions / Risk。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    brief = client.get(f"/api/v1/experiment-targets/{target['id']}/brief").json()["data"]
    for key in ["company", "opportunity", "evidences", "contacts", "outreach_draft", "validation_questions", "risk_notes", "statement_board"]:
        assert key in brief, f"Outreach Package 缺少 {key}"
