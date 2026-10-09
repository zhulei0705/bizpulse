"""T08.2 历史信号门回归（任务书二十三/二十六）：CONTRACT_AWARD 保持历史、不得触发当前机会。"""
import uuid
from datetime import datetime, timedelta, timezone

from app.services.actionability import compute_actionability_by_rules
from app.analyzers.opportunity.context import CompanyAnalysisContext, SignalContext


class _FakeRecord:
    def __init__(self, raw_text=None):
        self.raw_text = raw_text


class _FakeSignal:
    def __init__(self, signal_type, *, payload=None, published_at=None):
        self.id = f"sig_{uuid.uuid4().hex[:8]}"
        self.signal_type = signal_type
        self.payload_json = payload or {}
        self.published_at = published_at
        self.collected_at = datetime.now(timezone.utc)
        self.last_seen_at = None
        self.change_type = None
        self.change_value = None
        self.source_record = _FakeRecord()


NOW = datetime.now(timezone.utc)


def test_contract_award_is_historical_even_if_fresh():
    """刚抓到的中标公告也是历史事件（合同已授予）。"""
    s = _FakeSignal("CONTRACT_AWARD", published_at=NOW - timedelta(days=1))
    assert compute_actionability_by_rules(s) == "HISTORICAL_SIGNAL"


def test_historical_blocked_from_bundles():
    """历史信号不得进入任何 bundle 的 core/support 触发。"""
    from app.analyzers.opportunity.bundles import _is_current_signal

    s = _FakeSignal("CONTRACT_AWARD")
    assert _is_current_signal(s) is False
    # 当前可行动信号不受影响
    hiring = _FakeSignal("SALES_HIRING", published_at=NOW)
    assert _is_current_signal(hiring) is True


def test_historical_only_company_generates_no_candidate():
    """只有历史信号的企业：单信号兜底不产出（返回 only_historical_signals）。"""
    from app.analyzers.opportunity.bundles import build_signal_bundles, _is_current_signal

    company = type("C", (), {"company_name": "只有历史信号企业"})()
    ctx = CompanyAnalysisContext(company=company)
    sig = _FakeSignal("CONTRACT_AWARD")
    ctx.signals.append(SignalContext(signal=sig, source_grade="A"))

    assert build_signal_bundles(ctx) == []
    current = [s for s in ctx.signals if _is_current_signal(s.signal)]
    assert current == []


def test_historical_as_background_evidence_allowed():
    """历史信号保留在库中作为背景证据：不被删除、仍参与证据分（任务书二十三）。"""
    from app.services.actionability import is_actionable_for_validation

    assert is_actionable_for_validation("HISTORICAL_SIGNAL") is False
    # 状态本身仍为 APPROVED（保留），仅 actionability 门拦截
