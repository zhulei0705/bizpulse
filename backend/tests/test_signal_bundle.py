"""SignalBundleAnalyzer 测试：组合规则可解释、单信号兜底、采购组合为强购买信号。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.bundles import build_signal_bundles


def test_overseas_growth_bundle():
    """OVERSEAS_EXPANSION + SALES_HIRING → 海外客户开发需求置信度提升。"""
    ctx = make_company_context([
        make_signal("sig_1", "OVERSEAS_EXPANSION", confidence=78, grade="A", fact="设立海外办事处"),
        make_signal("sig_2", "SALES_HIRING", confidence=85, grade="B", fact="招聘海外销售5名"),
    ])
    bundles = build_signal_bundles(ctx)
    types = {b.bundle_type for b in bundles}
    assert "OVERSEAS_GROWTH" in types
    assert "SALES_SCALE_UP" in types
    og = next(b for b in bundles if b.bundle_type == "OVERSEAS_GROWTH")
    assert set(og.signal_types) >= {"OVERSEAS_EXPANSION", "SALES_HIRING"}
    assert "OVERSEAS_EXPANSION" in og.pain_categories
    assert og.explanation["rationale"], "组合必须可解释"
    assert og.confidence > 60


def test_purchase_ready_is_strongest():
    """PROCUREMENT/TENDER 组合 = 强购买信号，置信度应高于普通组合。"""
    ctx = make_company_context([
        make_signal("sig_1", "TENDER", confidence=85, grade="A", fact="发布招标公告"),
        make_signal("sig_2", "CRM_DEMAND", confidence=70, grade="B", fact="CRM 系统选型"),
    ])
    bundles = build_signal_bundles(ctx)
    purchase = next((b for b in bundles if b.bundle_type == "PURCHASE_READY"), None)
    assert purchase is not None
    others = [b.confidence for b in bundles if b.bundle_type != "PURCHASE_READY"]
    assert purchase.confidence >= max(others, default=0)


def test_single_signal_fallback_confidence_limited():
    """单信号（无组合）→ 仍产生候选线索，但置信度受限。"""
    ctx = make_company_context([
        make_signal("sig_1", "COST_PRESSURE", confidence=70, grade="C", fact="成本上涨"),
    ])
    bundles = build_signal_bundles(ctx)
    # COST_PRESSURE 是 COST_OPTIMIZATION 的 core → 命中但只有单信号
    cost = next((b for b in bundles if b.bundle_type == "COST_OPTIMIZATION"), None)
    assert cost is not None
    assert cost.confidence < 75  # 无支持信号，不能高分


def test_density_recorded_from_real_history():
    ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="B", age_days=1),
        make_signal("sig_2", "SALES_HIRING", confidence=80, grade="C", age_days=2),
        make_signal("sig_3", "FUNDING", confidence=85, grade="A", age_days=3),
    ])
    bundles = build_signal_bundles(ctx)
    sales = next(b for b in bundles if b.bundle_type == "SALES_SCALE_UP")
    assert sales.explanation["signal_count_7d"] >= 2
    assert sales.explanation["signal_count_30d"] >= 3


def test_no_signals_no_bundles():
    assert build_signal_bundles(make_company_context([])) == []
