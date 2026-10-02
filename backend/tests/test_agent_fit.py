"""AgentFitAnalyzer 测试：分类先验可解释、不因是 AI 产品全给高分、需求信号加分。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.agent_fit import compute_agent_fit


def test_category_priors_differ():
    invoice = compute_agent_fit(make_company_context([]), "INVOICE_AUTOMATION")
    recruitment = compute_agent_fit(make_company_context([]), "RECRUITMENT")
    compliance = compute_agent_fit(make_company_context([]), "COMPLIANCE")
    assert invoice.score >= 85
    assert recruitment.score <= 45
    assert compliance.score <= 40
    assert invoice.score > recruitment.score


def test_demand_signal_bonus():
    base_ctx = make_company_context([])
    demand_ctx = make_company_context([
        make_signal("sig_1", "AUTOMATION_DEMAND", confidence=75, grade="B"),
    ])
    base = compute_agent_fit(base_ctx, "PROCESS_AUTOMATION")
    with_demand = compute_agent_fit(demand_ctx, "PROCESS_AUTOMATION")
    assert with_demand.score > base.score
    assert any("AUTOMATION_DEMAND" in r for r in with_demand.reasons)


def test_manual_work_evidence_bonus():
    ctx = make_company_context([
        make_signal("sig_1", "MANUAL_WORK", confidence=70, grade="B", fact="人工录入报表"),
    ])
    result = compute_agent_fit(ctx, "PROCESS_AUTOMATION")
    assert any("MANUAL_WORK" in r for r in result.reasons)


def test_scores_in_range_and_explained():
    for category in ["PROCUREMENT", "SALES_EFFICIENCY", "OTHER"]:
        result = compute_agent_fit(make_company_context([]), category)
        assert 0 <= result.score <= 100
        assert result.reasons
