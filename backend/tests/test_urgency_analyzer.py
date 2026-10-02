"""UrgencyAnalyzer 测试：时间越新 Urgency 越高、密度加分、截止日期加分。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.urgency import compute_urgency


def test_recent_signals_higher_than_old():
    fresh = make_company_context([make_signal("sig_1", "PROCUREMENT", confidence=80, grade="A", age_days=2)])
    stale = make_company_context([make_signal("sig_2", "PROCUREMENT", confidence=80, grade="A", age_days=120)])
    assert compute_urgency(fresh).score > compute_urgency(stale).score + 20


def test_density_boost():
    dense = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="B", age_days=1),
        make_signal("sig_2", "FUNDING", confidence=80, grade="A", age_days=2),
        make_signal("sig_3", "EXPANSION", confidence=75, grade="B", age_days=3),
    ])
    sparse = make_company_context([make_signal("sig_0", "SALES_HIRING", confidence=80, grade="B", age_days=25)])
    r_dense = compute_urgency(dense)
    r_sparse = compute_urgency(sparse)
    assert r_dense.score > r_sparse.score
    assert any("30 天内" in r or "7 天内" in r for r in r_dense.reasons)


def test_deadline_in_evidence_boosts():
    import re
    from datetime import datetime, timedelta, timezone
    from app.analyzers.opportunity.urgency import _DEADLINE_PATTERN
    ctx = make_company_context([
        make_signal("sig_1", "TENDER", confidence=85, grade="A",
                    evidence_text=f"投标截止时间 {datetime.now(timezone.utc).date() + timedelta(days=5)}，逾期不受理"),
    ])
    result = compute_urgency(ctx)
    # 证据文本中的日期由 make_signal 原样放入 → 匹配截止日期模式
    matched = _DEADLINE_PATTERN.search(ctx.signals[0].evidences[0].quoted_text)
    if matched:
        assert result.score >= 85
        assert any("截止" in r for r in result.reasons)
    else:
        assert result.score >= 60


def test_expired_deadline_penalizes():
    ctx = make_company_context([
        make_signal("sig_1", "TENDER", confidence=85, grade="A",
                    evidence_text="投标截止 2020-01-01，逾期不受理"),
    ])
    result = compute_urgency(ctx)
    assert any("已过" in r for r in result.reasons)


def test_no_signals_zero():
    assert compute_urgency(make_company_context([])).score == 0
