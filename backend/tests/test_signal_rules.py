"""SignalRuleEngine 测试：规则命中、负面语境、行业泛指、来源类型优先、offset。"""
from app.analyzers.signal_rules import run_signal_rules


def test_sales_hiring_rule_hits_with_offset():
    text = "公司简介。我们正在招聘海外销售经理5名，工作地点上海。联系方式见页尾。"
    drafts = run_signal_rules(text, "OFFICIAL_WEBSITE")
    types = {d.candidate_type for d in drafts}
    assert "SALES_HIRING" in types
    draft = next(d for d in drafts if d.candidate_type == "SALES_HIRING")
    assert 0 <= draft.start_offset < draft.end_offset <= len(text)
    assert text[draft.start_offset:draft.end_offset].strip() == draft.evidence_text  # 摘录与 offset 一致


def test_negative_sentence_generates_nothing():
    """负面测试：『不计划招聘销售人员』不得生成 SALES_HIRING。"""
    text = "针对市场传闻，公司回应：目前没有招聘销售人员的计划，业务保持稳定。"
    drafts = run_signal_rules(text)
    assert "SALES_HIRING" not in {d.candidate_type for d in drafts}
    assert "HIRING" not in {d.candidate_type for d in drafts}


def test_negative_funding_not_detected():
    text = "该公司澄清：并未启动新一轮融资，也未聘请财务顾问。"
    drafts = run_signal_rules(text)
    assert "FUNDING" not in {d.candidate_type for d in drafts}


def test_generic_industry_subject_not_attributed():
    """负面测试：『行业普遍增加AI投资』不指向该企业 → 不生成该企业 AI 类信号。"""
    text = "据行业研究报告显示，人工智能行业普遍增加AI投资，市场整体呈上升趋势。本企业提供物流服务。"
    drafts = run_signal_rules(text)
    assert "AI_DEMAND" not in {d.candidate_type for d in drafts}
    assert "AI_TRANSFORMATION" not in {d.candidate_type for d in drafts}


def test_source_type_hint_boosts_priority():
    text = "某单位公开采购信息系统服务，预算另行公布。同时发布招聘信息。"
    gov = run_signal_rules(text, "GOVERNMENT")
    web = run_signal_rules(text, "OFFICIAL_WEBSITE")
    gov_proc = next((d for d in gov if d.candidate_type == "PROCUREMENT"), None)
    web_proc = next((d for d in web if d.candidate_type == "PROCUREMENT"), None)
    assert gov_proc and web_proc
    assert gov_proc.rule_confidence > web_proc.rule_confidence  # 来源类型加成


def test_specific_hiring_shadows_generic():
    text = "急聘算法工程师与海外销售总监若干，欢迎投递。"
    drafts = run_signal_rules(text)
    types = {d.candidate_type for d in drafts}
    assert "SALES_HIRING" in types and "AI_HIRING" in types
    assert "HIRING" not in types  # 泛化类型被具体类型覆盖


def test_new_factory_and_tender():
    text = "公司宣布新建工厂扩大产能。同期某市政项目发布招标公告。"
    drafts = run_signal_rules(text)
    types = {d.candidate_type for d in drafts}
    assert "NEW_FACTORY" in types
    assert "TENDER" in types


def test_empty_text_returns_empty():
    assert run_signal_rules("") == []
    assert run_signal_rules("   \n  ") == []
