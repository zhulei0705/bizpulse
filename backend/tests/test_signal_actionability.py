"""T08.2 Signal Actionability Analyzer 回归（任务书二十二~二十五：规则优先，LLM不独断）。"""
from datetime import datetime, timedelta, timezone

from app.services.actionability import (
    compute_actionability_by_rules,
    compute_signal_actionability,
    record_signal_actionability,
)


class _FakeRecord:
    def __init__(self, raw_text=None):
        self.raw_text = raw_text


class _FakeSignal:
    """最小信号桩（不触库；时间字段可控）。"""

    def __init__(self, signal_type, *, published_at=None, collected_at=None,
                 payload=None, raw_text=None):
        self.signal_type = signal_type
        self.published_at = published_at
        self.collected_at = collected_at or datetime.now(timezone.utc)
        self.payload_json = payload or {}
        self.source_record = _FakeRecord(raw_text)


NOW = datetime.now(timezone.utc)


def test_hiring_is_actionable_now():
    """近期招聘 = 企业当前扩张行为 → ACTIONABLE_NOW。"""
    s = _FakeSignal("SALES_HIRING", published_at=NOW - timedelta(days=3))
    assert compute_actionability_by_rules(s) == "ACTIONABLE_NOW"


def test_hiring_without_date_is_unknown_freshness():
    """采集时间不能证明无日期招聘仍有效。"""
    s = _FakeSignal("HIRING")
    assert compute_actionability_by_rules(s) == "WATCH"


def test_old_hiring_becomes_watch():
    """超过180天且无新证据的招聘 → WATCH。"""
    s = _FakeSignal("AI_HIRING", published_at=NOW - timedelta(days=200))
    assert compute_actionability_by_rules(s) == "WATCH"


def test_recent_news_event_actionable():
    """90天内的新产品/新市场事件 → ACTIONABLE_NOW。"""
    for t in ("NEW_PRODUCT", "NEW_MARKET", "OVERSEAS_EXPANSION", "NEW_FACTORY"):
        s = _FakeSignal(t, published_at=NOW - timedelta(days=10))
        assert compute_actionability_by_rules(s) == "ACTIONABLE_NOW", t


def test_old_news_event_watch():
    """90天前的事件 → WATCH（不再是当下行动窗口）。"""
    s = _FakeSignal("NEW_PRODUCT", published_at=NOW - timedelta(days=120))
    assert compute_actionability_by_rules(s) == "WATCH"


def test_undated_event_is_watch():
    """官网仍展示不能证明事件近期。"""
    s = _FakeSignal("PARTNERSHIP")
    assert compute_actionability_by_rules(s) == "WATCH"


def test_open_tender_actionable_closed_not():
    """招标：截止未到 → ACTIONABLE_NOW；已过 → NOT_ACTIONABLE。"""
    future = (NOW + timedelta(days=20)).strftime("%Y年%m月%d日 %H:%M")
    past = (NOW - timedelta(days=20)).strftime("%Y年%m月%d日 %H:%M")
    open_text = f"公开招标公告 投标截止时间 {future}"
    closed_text = f"公开招标公告 投标截止时间 {past}"
    assert compute_actionability_by_rules(_FakeSignal("TENDER", raw_text=open_text)) == "ACTIONABLE_NOW"
    assert compute_actionability_by_rules(_FakeSignal("TENDER", raw_text=closed_text)) == "NOT_ACTIONABLE"


def test_contract_award_stays_historical():
    """CONTRACT_AWARD 恒为 HISTORICAL（供应商侧），不受新鲜度影响（任务书二十三）。"""
    s = _FakeSignal("CONTRACT_AWARD", published_at=NOW)
    assert compute_actionability_by_rules(s) == "HISTORICAL_SIGNAL"


def test_audit_result_takes_precedence():
    """t08_audit 审计结果优先于规则重算（幂等）。"""
    s = _FakeSignal("CONTRACT_AWARD", payload={
        "t08_audit": {"subject_role": "SUPPLIER", "procurement_status": "AWARDED",
                      "actionability_status": "HISTORICAL_SIGNAL"}})
    assert compute_signal_actionability(None, s) == "HISTORICAL_SIGNAL"


def test_explicit_actionability_block_used():
    """payload.actionability 显式块（T08.2 写入）优先于规则重算。"""
    s = _FakeSignal("NEW_PRODUCT", payload={"actionability": {"status": "WATCH",
                                                              "computed_by": "rule_actionability_v1"}})
    assert compute_signal_actionability(None, s) == "WATCH"


def test_record_actionability_writes_payload():
    """record_signal_actionability 把判定写入 payload（幂等，不覆盖已有）。"""
    persisted = {}

    class _DB:
        def flush(self):
            persisted["flushed"] = True

    s = _FakeSignal("SALES_HIRING", published_at=NOW)
    status = record_signal_actionability(_DB(), s)
    assert status == "ACTIONABLE_NOW"
    assert s.payload_json["actionability"]["status"] == "ACTIONABLE_NOW"
    assert s.payload_json["actionability"]["computed_by"] == "rule_actionability_v1"
    # 幂等：已有结果不覆盖
    s.payload_json["actionability"]["status"] = "WATCH"
    assert record_signal_actionability(_DB(), s) == "WATCH"
