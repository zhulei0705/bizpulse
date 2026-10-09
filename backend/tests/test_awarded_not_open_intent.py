"""T08.1 回归：中标公告绝不能抬升购买意图（AWARDED ≠ active purchase intent）。"""
from datetime import datetime, timezone

from app.analyzers.opportunity.context import CompanyAnalysisContext, SignalContext
from app.analyzers.opportunity.intent import compute_intent
from app.models.company import Company


def _ctx(signal_types: list[str]) -> CompanyAnalysisContext:
    company = Company(company_name="意图测试企业", normalized_name="意图测试企业",
                      organization_type="COMPANY")
    ctx = CompanyAnalysisContext(company=company)
    for t in signal_types:
        class _S:
            pass
        signal = _S()
        signal.signal_type = t
        signal.change_type = None
        signal.change_value = None
        signal.last_seen_at = None
        signal.collected_at = datetime.now(timezone.utc)
        ctx.signals.append(SignalContext(signal=signal, source_grade="A"))
    return ctx


def test_award_only_company_has_no_direct_purchase_intent():
    """只有 CONTRACT_AWARD 的企业：无直接购买信号，不得因中标事件产生高购买意图。"""
    result = compute_intent(_ctx(["CONTRACT_AWARD"]))
    assert result.extra["direct_purchase"] == 0
    assert any("不计入购买意图" in r for r in result.reasons)
    # 中标是既成事实：意图分不得进入"高意图"区间（<60）
    assert result.score < 60


def test_award_does_not_override_tender_absence():
    """CONTRACT_AWARD 不等于 TENDER：直接购买信号集合不得包含它。"""
    from app.core.constants import DIRECT_PURCHASE_SIGNAL_TYPES
    assert "CONTRACT_AWARD" not in DIRECT_PURCHASE_SIGNAL_TYPES


def test_tender_still_counts_as_direct_purchase():
    """对照：真实招标（未截止）信号仍然是直接购买信号。"""
    result = compute_intent(_ctx(["TENDER"]))
    assert result.extra["direct_purchase"] == 100


def test_award_plus_tender_intent_comes_from_tender():
    """企业同时有中标历史与新招标时：意图分来源是 TENDER（直接购买），不是中标历史。"""
    result = compute_intent(_ctx(["CONTRACT_AWARD", "TENDER"]))
    assert result.extra["direct_purchase"] == 100
    assert any("不计入购买意图" in r for r in result.reasons)
