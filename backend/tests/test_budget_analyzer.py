"""BudgetAnalyzer 测试：金额只能来自原文、无证据必须 UNKNOWN、禁止编造。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.budget import compute_budget


def test_amount_extracted_from_original_text():
    """关键测试2（部分）：公开采购 + 明确预算 → Budget 明确。"""
    ctx = make_company_context([
        make_signal("sig_p", "TENDER", confidence=85, grade="A",
                    evidence_text="项目预算：500万元，采购智能客服系统"),
    ])
    result = compute_budget(ctx, None)
    assert result.amounts, "应从原文提取到金额"
    assert result.amounts[0]["amount_wan"] == 500
    assert result.score >= 75
    assert result.budget_level in {"MEDIUM", "HIGH"}
    assert "原文明确预算" in " ".join(result.reasons)


def test_amount_from_full_record_text_with_currency_symbol():
    """真实场景（ccgp 公告）："预算金额 ￥400.000000万元" 出现在完整原文而非证据摘录窗口。"""
    from types import SimpleNamespace

    ctx = make_company_context([
        make_signal("sig_r", "TENDER", confidence=85, grade="A",
                    evidence_text="公开招标公告：高性能计算机时采购项目"),
    ])
    ctx.signals[0].record = SimpleNamespace(
        id="rec_real", url="http://ccgp.example/announce",
        published_at=None,
        raw_text="提交投标文件截止时间：2026年10月21日 预算金额 ￥400.000000万元（人民币） 采购单位：某研究所",
    )
    result = compute_budget(ctx, None)
    assert result.amounts, "应从完整原文提取到金额"
    assert abs(result.amounts[0]["amount_wan"] - 400) < 0.01
    assert result.score >= 80
    assert result.budget_level in {"MEDIUM", "HIGH"}
    assert result.amounts[0]["source_record_id"] == "rec_real"


def test_no_amount_no_fabrication():
    """关键测试3：原文没有预算 → Budget Analyzer 不能创造金额。"""
    ctx = make_company_context([
        make_signal("sig_n", "TENDER", confidence=80, grade="A",
                    evidence_text="发布采购公告，采购一批办公设备"),
    ])
    result = compute_budget(ctx, None)
    assert result.amounts == [], "无金额原文时禁止提取金额"
    assert result.budget_level == "UNKNOWN"
    assert "不猜测金额" in " ".join(result.reasons)


def test_funding_proxy():
    ctx = make_company_context([
        make_signal("sig_f", "FUNDING", confidence=85, grade="A", fact="完成A轮融资", age_days=5),
    ])
    result = compute_budget(ctx, None)
    assert result.score >= 60
    assert "融资" in " ".join(result.reasons)


def test_employee_range_proxy():
    ctx = make_company_context([], employee_range="1000人以上")
    result = compute_budget(ctx, None)
    assert result.score >= 60
    assert "1000" in " ".join(result.reasons) or "企业规模" in " ".join(result.reasons)


def test_no_evidence_low_confidence():
    ctx = make_company_context([
        make_signal("sig_1", "NEW_PRODUCT", confidence=60, grade="D", fact="普通新闻", age_days=100),
    ])
    result = compute_budget(ctx, None)
    assert result.budget_level == "UNKNOWN"
    assert result.score <= 50  # 仅弱代理信号（小企业规模），不得高分


def test_amount_requires_procurement_context():
    """金额模式必须有采购语境（防止把融资新闻里的数字当采购预算）。"""
    ctx = make_company_context([
        make_signal("sig_1", "NEW_PRODUCT", confidence=70, grade="B",
                    evidence_text="产品定价金额：300万元"),
    ])
    result = compute_budget(ctx, None)
    assert result.amounts == []
