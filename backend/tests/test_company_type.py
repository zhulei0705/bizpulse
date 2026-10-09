"""T08 组织类型测试：通过真实上下文规则判断；无法确认 UNKNOWN。"""
from app.services.campaign_runner import _organization_type_from_notice


def test_org_type_from_supplier_name():
    assert _organization_type_from_notice("", "北京华谱科技有限公司") == "COMPANY"
    assert _organization_type_from_notice("", "清华大学") == "UNIVERSITY"
    assert _organization_type_from_notice("", "中科院理论物理研究所") == "RESEARCH_INSTITUTE"
    assert _organization_type_from_notice("", "北京协和医院") == "HOSPITAL"


def test_org_type_unknown_when_cannot_confirm():
    """无法确认时保持 UNKNOWN，禁止 AI 随意判断（任务书十二）。"""
    assert _organization_type_from_notice("", "某某采购项目") == "UNKNOWN"
    assert _organization_type_from_notice("", "") == "UNKNOWN"


def test_org_type_government_from_context():
    assert _organization_type_from_notice("某市财政局政府采购公告", "某某单位") == "GOVERNMENT"
