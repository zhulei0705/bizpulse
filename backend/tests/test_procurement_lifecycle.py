"""T08.1 采购事件生命周期回归（任务书第五节：ANNOUNCED/OPEN/CLOSED/AWARDED/CANCELLED...）。"""
from datetime import datetime, timedelta

from app.services.procurement_parser import (
    derive_actionability,
    parse_procurement_lifecycle,
)


def test_awarded_on_result_notice():
    text = "某项目中标公告 三、中标（成交）信息 供应商名称：X公司"
    assert parse_procurement_lifecycle(text) == "AWARDED"


def test_awarded_on_chengjiao_notice():
    text = "某项目成交公告 三、成交信息 供应商名称：X公司"
    assert parse_procurement_lifecycle(text) == "AWARDED"


def test_cancelled_on_biabiao():
    text = "某项目废标公告 本项目废标，重新组织招标"
    assert parse_procurement_lifecycle(text) == "CANCELLED"


def test_cancelled_on_liubiao():
    text = "某项目流标公告"
    assert parse_procurement_lifecycle(text) == "CANCELLED"


def test_open_when_deadline_in_future():
    text = "某项目公开招标公告 投标截止时间 2026年12月01日 09:30"
    future = datetime(2026, 10, 5, 12, 0, 0)
    assert parse_procurement_lifecycle(text, deadline=datetime(2026, 12, 1, 9, 30), now=future) == "OPEN"


def test_closed_when_deadline_passed():
    text = "某项目公开招标公告 投标截止时间 2026年09月01日 09:30"
    now = datetime(2026, 10, 5, 12, 0, 0)
    assert parse_procurement_lifecycle(text, deadline=datetime(2026, 9, 1, 9, 30), now=now) == "CLOSED"


def test_announced_without_deadline():
    text = "某项目采购公告 欢迎符合条件的供应商参与"
    assert parse_procurement_lifecycle(text) == "ANNOUNCED"


def test_unknown_for_empty_or_irrelevant():
    assert parse_procurement_lifecycle(None) == "UNKNOWN"
    assert parse_procurement_lifecycle("今天天气不错") == "UNKNOWN"


def test_awarded_beats_deadline_logic():
    """已出中标结果的公告即使原文残留截止时间，生命周期也是 AWARDED。"""
    text = "某项目中标公告 投标截止时间 2026年09月01日 09:30 三、中标（成交）信息 供应商名称：X公司"
    now = datetime(2026, 10, 5)
    assert parse_procurement_lifecycle(text, deadline=datetime(2026, 9, 1), now=now) == "AWARDED"


def test_actionability_mapping():
    assert derive_actionability("OPEN", "BUYER") == "ACTIONABLE_NOW"
    assert derive_actionability("OPEN", "SUPPLIER") == "ACTIONABLE_NOW"
    assert derive_actionability("ANNOUNCED", "BUYER") == "WATCH"
    assert derive_actionability("CLOSED", "BUYER") == "NOT_ACTIONABLE"
    assert derive_actionability("EXPIRED", "BUYER") == "NOT_ACTIONABLE"
    assert derive_actionability("CANCELLED", "BUYER") == "NOT_ACTIONABLE"
    assert derive_actionability("AWARDED", "SUPPLIER") == "HISTORICAL_SIGNAL"
    assert derive_actionability("AWARDED", "BUYER") == "NOT_ACTIONABLE"
    assert derive_actionability("UNKNOWN", "BUYER") == "UNKNOWN"


def test_now_defaults_to_current_time():
    """now 缺省时按当前时间判断（过去截止 → CLOSED）。"""
    past = (datetime.now() - timedelta(days=10)).strftime("%Y年%m月%d日 %H:%M")
    text = f"某项目公开招标公告 投标截止时间 {past}"
    assert parse_procurement_lifecycle(text, deadline=datetime.now() - timedelta(days=10)) == "CLOSED"
