"""T08.0 政府采购公告结构化解析回归（真实公告正文样例：华南理工/清华/中科院）。"""
from datetime import datetime

from app.services.procurement_parser import (
    extract_procurement_contacts,
    parse_announcement_time,
    parse_budget_amount,
    parse_deadline,
    parse_purchaser,
    parse_project_name,
    parse_category,
)

# 真实 ccgp 公告正文结构样例（三段式：公告头 + 采购人信息 + 代理机构信息）
REAL_NOTICE = """
清华大学67GHz矢量信号发生器中标公告
项目编号：SCUT-HW-ZB20260001
项目名称：67GHz矢量信号发生器采购项目
采购品目：A0201仪器仪表
预算金额：￥1,280,000.00
采购人：清华大学
地址：北京市海淀区清华大学
联系方式：项目联系人张老师 010-62785000
代理机构名称：中招国际招标有限公司
代理机构联系方式：代理联系人李工 010-68587000 ybl@cntcitc.com.cn
公告时间：2026年09月30日 19:46
投标截止时间：2026年09月20日 09:30
"""


def test_announcement_time_parsed_from_body():
    """P0-5：公告时间"2026年09月30日 19:46"必须被解析为 published_at。"""
    parsed = parse_announcement_time(REAL_NOTICE)
    assert parsed is not None
    assert parsed.year == 2026 and parsed.month == 9 and parsed.day == 30
    assert parsed.hour == 19 and parsed.minute == 46


def test_deadline_parsed():
    parsed = parse_deadline(REAL_NOTICE)
    assert parsed is not None
    assert parsed.day == 20


def test_budget_amount_parsed():
    assert parse_budget_amount(REAL_NOTICE) == 1280000.0


def test_purchaser_and_project_and_category():
    assert parse_purchaser(REAL_NOTICE) == "清华大学"
    assert "67GHz矢量信号发生器" in (parse_project_name(REAL_NOTICE) or "")
    assert parse_category(REAL_NOTICE) == "A0201仪器仪表"


def test_contacts_distinguish_purchaser_and_agency():
    """P0-6：采购人联系人与代理机构联系人严格区分，不得错归属。"""
    drafts = extract_procurement_contacts(REAL_NOTICE)
    types = {d.contact_type for d in drafts}
    assert "PURCHASER_CONTACT" in types
    assert "AGENCY_CONTACT" in types
    purchaser = next(d for d in drafts if d.contact_type == "PURCHASER_CONTACT")
    agency = next(d for d in drafts if d.contact_type == "AGENCY_CONTACT")
    # 采购人联系人归属采购单位
    assert purchaser.organization_name == "清华大学"
    assert purchaser.phone == "010-62785000"
    # 代理机构联系人归属代理公司（不是采购单位）
    assert agency.organization_name == "中招国际招标有限公司"
    assert agency.email == "ybl@cntcitc.com.cn"


def test_missing_fields_stay_none():
    """解析不到的字段保持 None（不猜测）。"""
    assert parse_announcement_time("无时间信息的正文") is None
    assert parse_budget_amount("没有金额") is None
    assert parse_purchaser("没有采购人字段") is None
