"""T08.1 主体角色判定回归（任务书第三节：采购方与中标方绝对不能混）。"""
from app.services.procurement_parser import (
    classify_subject_role,
    derive_actionability,
    parse_buyer_organization,
    parse_awarded_suppliers_with_amounts,
)

NOTICE = """某项目中标公告
公告信息： 采购项目名称 实验室设备采购项目 采购单位 某甲大学 行政区域 北京市 公告时间 2026年09月30日 10:00
三、中标（成交）信息 供应商名称：乙科技有限公司 供应商地址：某市某区 中标（成交）金额：500.0000000（万元）
代理机构名称：某招标代理有限公司
1.采购人信息 名 称：某甲大学"""

NOTICE_UNIVERSITY_SUPPLIER = """某采购项目中标结果公告
公告信息： 采购项目名称 智能疫苗和抗体筛选模块采购项目 采购单位 zycgr22011901 行政区域 广州市 公告时间 2026年09月30日 18:00
三、中标（成交）信息 供应商名称：上海交通大学 供应商地址：上海市华山路1954号 中标（成交）金额：718.3200000（万元）"""


def _suppliers(text):
    return parse_awarded_suppliers_with_amounts(text)


def test_awarded_supplier_role():
    buyer = parse_buyer_organization(NOTICE)
    assert buyer["buyer"] == "某甲大学"
    role = classify_subject_role("乙科技有限公司", buyer, _suppliers(NOTICE))
    assert role == "SUPPLIER"


def test_buyer_role_not_supplier():
    buyer = parse_buyer_organization(NOTICE)
    role = classify_subject_role("某甲大学", buyer, _suppliers(NOTICE))
    assert role == "BUYER"
    # 采购方绝不能被识别成中标供应商
    assert classify_subject_role("某甲大学", buyer, _suppliers(NOTICE)) != "SUPPLIER"


def test_procurement_agency_role():
    buyer = parse_buyer_organization(NOTICE)
    role = classify_subject_role("某招标代理有限公司", buyer, _suppliers(NOTICE))
    assert role == "PROCUREMENT_AGENCY"


def test_unknown_subject_is_other():
    buyer = parse_buyer_organization(NOTICE)
    assert classify_subject_role("无关的某家公司", buyer, _suppliers(NOTICE)) == "OTHER"
    assert classify_subject_role(None, buyer, _suppliers(NOTICE)) == "OTHER"


def test_university_can_be_supplier():
    """高校可以作为中标供应商（真实案例：上海交大中标设备供货项目）——角色判定不因名称误判。"""
    buyer = parse_buyer_organization(NOTICE_UNIVERSITY_SUPPLIER)
    role = classify_subject_role("上海交通大学", buyer, _suppliers(NOTICE_UNIVERSITY_SUPPLIER))
    assert role == "SUPPLIER"
    # 采购人是代码名 zycgr22011901，不是上海交大
    assert buyer["buyer"] == "zycgr22011901"


def test_name_matching_ignores_case_and_spaces():
    buyer = {"buyer": "A 大学", "executing_agency": None, "procurement_agency": None}
    suppliers = [{"supplier_name": "B科技有限公司", "award_amount": 1.0}]
    assert classify_subject_role("b科技 有限公司", buyer, suppliers) == "SUPPLIER"


def test_awarded_supplier_is_historical_signal_not_open_intent():
    """中标 ≠ 正在寻找供应商：供应商侧是历史能力证据，不是可参与采购。"""
    assert derive_actionability("AWARDED", "SUPPLIER") == "HISTORICAL_SIGNAL"


def test_awarded_buyer_enters_procurement_history():
    """采购方已完成采购 → 对当前采购不可行动（进入采购历史）。"""
    assert derive_actionability("AWARDED", "BUYER") == "NOT_ACTIONABLE"
