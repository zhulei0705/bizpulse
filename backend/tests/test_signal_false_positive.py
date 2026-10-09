"""T08.0 P0-3 Signal 误判回归：采购公告只产 PROCUREMENT/TENDER，不产 NEW_PRODUCT/POLICY_IMPACT。"""
from app.analyzers.signal_rules import is_procurement_context, run_signal_rules
from app.services import extractor
from app.services.extractor import FetchedPage

# 真实采购公告正文特征（含"采购产品"等易误触词）
PROCUREMENT_NOTICE = """
华南理工大学低温超高真空扫描隧道显微镜（SCUT-HW-ZB20260011号）公开招标公告
项目名称：低温超高真空扫描隧道显微镜采购项目
预算金额：￥9,800,000
一、采购需求：采购超高真空扫描隧道显微镜一套，用于材料表面分析。投标人应提供仪器采购产品的完整技术方案。
二、申请人的资格要求：本项目不允许转包。国家相关规定出台前按现行规定执行。
公告时间：2026年09月30日
"""

PRODUCT_NEWS = """
恒锋智造正式推出新一代智能客服平台，新品上市发布会在上海举行。
公司宣布发布全新产品线，面向海外市场。
"""


def test_procurement_context_detected():
    assert is_procurement_context(PROCUREMENT_NOTICE) is True
    assert is_procurement_context(PRODUCT_NEWS) is False


def test_notice_only_produces_procurement_family():
    """采购公告的信号类型必须在采购族内。"""
    allowed = {"PROCUREMENT", "TENDER", "SUPPLIER_SEARCH", "AI_DEMAND", "CRM_DEMAND", "ERP_DEMAND", "AUTOMATION_DEMAND"}
    hits = extractor.extract_signal_hits(FetchedPage(
        url="http://www.ccgp.gov.cn/x", final_url="http://www.ccgp.gov.cn/x",
        status_code=200, content_type="text/html", title="华南理工大学显微镜公开招标公告",
        text=PROCUREMENT_NOTICE, html="",
    ))
    assert hits, "应产生采购族信号"
    for hit in hits:
        assert hit.signal_type in allowed, f"采购公告误产信号：{hit.signal_type}"
    assert {"PROCUREMENT", "TENDER"} <= {h.signal_type for h in hits}


def test_t04_engine_same_suppression():
    drafts = run_signal_rules(PROCUREMENT_NOTICE, source_type="GOVERNMENT")
    allowed = {"PROCUREMENT", "TENDER", "SUPPLIER_SEARCH", "AI_DEMAND", "CRM_DEMAND", "ERP_DEMAND", "AUTOMATION_DEMAND"}
    for d in drafts:
        assert d.candidate_type in allowed, f"T04 引擎采购公告误产：{d.candidate_type}"


def test_no_new_product_from_procurement():
    """不能因为"采购产品"生成 NEW_PRODUCT（任务书 P0-3）。"""
    hits = extractor.extract_signal_hits(FetchedPage(
        url="x", final_url="x", status_code=200, content_type="text/html",
        title="采购公告", text=PROCUREMENT_NOTICE, html="",
    ))
    assert all(h.signal_type != "NEW_PRODUCT" for h in hits)
    drafts = run_signal_rules(PROCUREMENT_NOTICE, source_type="GOVERNMENT")
    assert all(d.candidate_type != "NEW_PRODUCT" for d in drafts)


def test_no_policy_impact_from_procurement():
    """不能因为招标公告生成 POLICY_IMPACT。"""
    hits = extractor.extract_signal_hits(FetchedPage(
        url="x", final_url="x", status_code=200, content_type="text/html",
        title="中标公告", text=PROCUREMENT_NOTICE, html="",
    ))
    assert all(h.signal_type != "POLICY_IMPACT" for h in hits)
    drafts = run_signal_rules(PROCUREMENT_NOTICE, source_type="GOVERNMENT")
    assert all(d.candidate_type != "POLICY_IMPACT" for d in drafts)


def test_product_news_still_produces_new_product():
    """非采购上下文的企业新品新闻仍正常产生 NEW_PRODUCT（不误伤）。"""
    hits = extractor.extract_signal_hits(FetchedPage(
        url="x", final_url="x", status_code=200, content_type="text/html",
        title="恒锋智造新品发布", text=PRODUCT_NEWS, html="",
    ))
    assert any(h.signal_type == "NEW_PRODUCT" for h in hits)


def test_evidence_in_notice_is_substantive():
    """采购公告信号的 Evidence 必须是实质内容，不是导航/footer。"""
    notice_with_noise = (
        "9289 首页 政采法规 购买服务 监督检查 信息公告 国际专栏 当前位置\n"
        + PROCUREMENT_NOTICE
        + "\n财政部唯一指定政府采购信息网络发布媒体 服务热线：400-810-1996"
    )
    hits = extractor.extract_signal_hits(FetchedPage(
        url="x", final_url="x", status_code=200, content_type="text/html",
        title="招标公告", text=notice_with_noise, html="",
    ))
    for hit in hits:
        assert "首页 »" not in hit.excerpt
        assert "服务热线" not in hit.excerpt
        assert "政采法规" not in hit.excerpt
