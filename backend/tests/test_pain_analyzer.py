"""PainAnalyzer 测试：PainPoint 必须是推断（INFERENCE）、多信号印证提升置信度、分类对齐枚举。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.pain import infer_pains_from_signals
from app.core.constants import PAIN_CATEGORIES


def _signals(*specs):
    return [make_signal(f"sig_{i}", t, confidence=c, grade=g, fact=f)
            for i, (t, c, g, f) in enumerate(specs)]


def test_pain_is_inference_not_fact():
    """事实：企业30天内新增10个销售岗位 → AI 只能推断痛点，不能陈述为事实。"""
    ctx = make_company_context(_signals(
        ("SALES_HIRING", 85, "A", "官网30天内新增10个海外销售岗位"),
    ))
    pains = infer_pains_from_signals(ctx)
    assert pains, "应推断出至少一个 PainPoint"
    pain = pains[0]
    assert pain.category in PAIN_CATEGORIES
    # 推断措辞：描述中必须出现"可能"，不得断言
    assert "可能" in pain.description
    assert "AI 推断" in pain.reasoning_summary or "推断" in pain.reasoning_summary
    # 必须关联支持信号
    assert pain.signal_ids


def test_pain_categories_aligned_to_enum():
    ctx = make_company_context(_signals(
        ("SALES_HIRING", 85, "A", "招聘海外销售"),
        ("CUSTOMER_COMPLAINT", 70, "B", "客户投诉增加"),
        ("COST_PRESSURE", 72, "B", "原材料涨价"),
        ("DATA_PROBLEM", 68, "C", "数据孤岛"),
    ))
    categories = {p.category for p in infer_pains_from_signals(ctx)}
    assert categories <= set(PAIN_CATEGORIES.keys())
    assert "CUSTOMER_ACQUISITION" in categories or "SALES_EFFICIENCY" in categories
    assert "CUSTOMER_SERVICE" in categories
    assert "COST_REDUCTION" in categories
    assert "DATA_MANAGEMENT" in categories


def test_multi_signal_boosts_confidence():
    single = make_company_context(_signals(("SALES_HIRING", 80, "B", "招聘销售")))
    multi = make_company_context(_signals(
        ("SALES_HIRING", 80, "B", "招聘销售"),
        ("FUNDING", 85, "A", "完成A轮融资"),
    ))
    pain_single = {p.category: p for p in infer_pains_from_signals(single)}
    pain_multi = {p.category: p for p in infer_pains_from_signals(multi)}
    # 同分类（CUSTOMER_ACQUISITION）多信号印证后置信度更高
    cat = "CUSTOMER_ACQUISITION"
    if cat in pain_single and cat in pain_multi:
        assert pain_multi[cat].confidence > pain_single[cat].confidence


def test_bundle_pains_included():
    from app.analyzers.opportunity.bundles import BundleDraft

    ctx = make_company_context(_signals(
        ("OVERSEAS_EXPANSION", 78, "A", "设立海外办事处"),
    ))
    bundle = BundleDraft(
        bundle_type="OVERSEAS_GROWTH",
        signal_ids=[s.signal.id for s in ctx.signals],
        signal_types=["OVERSEAS_EXPANSION"],
        pain_categories=["OVERSEAS_EXPANSION", "CUSTOMER_ACQUISITION"],
        confidence=70,
    )
    pains = infer_pains_from_signals(ctx, bundle)
    categories = {p.category for p in pains}
    assert "OVERSEAS_EXPANSION" in categories


def test_no_signals_no_pains():
    ctx = make_company_context([])
    assert infer_pains_from_signals(ctx) == []
