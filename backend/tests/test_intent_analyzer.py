"""IntentAnalyzer 测试：直接购买信号 >> 普通新闻；组成权重可解释。"""
from tests.helpers_t05 import make_company_context, make_signal


def test_direct_purchase_beats_plain_news():
    """关键测试2（部分）：公开采购 + A 级来源的 Intent 必须明显高于普通行业新闻。"""
    procurement = make_company_context([
        make_signal("sig_t", "TENDER", confidence=88, grade="A", fact="发布招标公告，采购客服系统"),
    ])
    news = make_company_context([
        make_signal("sig_n", "NEW_PRODUCT", confidence=70, grade="C", fact="行业新闻：某公司发布新品", age_days=45),
    ])
    assert procurement.signal_types == {"TENDER"}
    assert news.signal_types == {"NEW_PRODUCT"}
    intent_proc = __import__("app.analyzers.opportunity.intent", fromlist=["compute_intent"]).compute_intent(procurement)
    intent_news = __import__("app.analyzers.opportunity.intent", fromlist=["compute_intent"]).compute_intent(news)
    assert intent_proc.score > intent_news.score + 20
    assert intent_proc.extra["direct_purchase"] > 0
    assert intent_news.extra["direct_purchase"] == 0


def test_intent_score_in_range_with_reasons():
    ctx = make_company_context([
        make_signal("sig_1", "PROCUREMENT", confidence=80, grade="B", fact="公开采购"),
        make_signal("sig_2", "EFFICIENCY_PROBLEM", confidence=70, grade="B", fact="人工处理效率低"),
    ])
    from app.analyzers.opportunity.intent import compute_intent
    result = compute_intent(ctx)
    assert 0 <= result.score <= 100
    assert result.reasons, "必须给出可解释依据"


def test_multi_signal_supported():
    ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="B"),
        make_signal("sig_2", "FUNDING", confidence=85, grade="A"),
        make_signal("sig_3", "NEW_MARKET", confidence=70, grade="B"),
    ])
    from app.analyzers.opportunity.intent import compute_intent
    result = compute_intent(ctx)
    assert result.extra["multi_signal"] >= 60


def test_single_old_weak_news_low_intent():
    ctx = make_company_context([
        make_signal("sig_1", "NEW_PRODUCT", confidence=60, grade="D", fact="转载新闻", age_days=120),
    ])
    from app.analyzers.opportunity.intent import compute_intent
    result = compute_intent(ctx)
    assert result.score < 50
