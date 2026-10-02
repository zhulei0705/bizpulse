"""UrgencyAnalyzer —— 时间紧迫度（T05）。

判断问题是不是"现在发生"：新信号越近 Urgency 越高；
30 天内多次变化、采购/招标截止日期、岗位快速增加、融资后快速扩张都会加分。
全部依据真实时间数据。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.analyzers.opportunity.context import CompanyAnalysisContext

_DEADLINE_PATTERN = re.compile(r"(截止|截至|closing)[^。；\n]{0,24}?(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})")


@dataclass
class UrgencyResult:
    score: int
    reasons: list[str] = field(default_factory=list)


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_urgency(ctx: CompanyAnalysisContext, *, now: datetime | None = None) -> UrgencyResult:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []

    # 1) 最新信号距今天数（时间越新 Urgency 越高）
    newest = ctx.newest_signal_at
    if newest is None:
        return UrgencyResult(score=0, reasons=["无已批准信号"])
    age_days = (now - _ensure_utc(newest)).days
    if age_days <= 7:
        score = 85
        reasons.append(f"最新信号 {age_days} 天前（7 天内强信号）")
    elif age_days <= 30:
        score = 65
        reasons.append(f"最新信号 {age_days} 天前（30 天内）")
    elif age_days <= 90:
        score = 45
        reasons.append(f"最新信号 {age_days} 天前（90 天内）")
    else:
        score = 25
        reasons.append(f"最新信号 {age_days} 天前（较旧）")

    # 2) 时间密度：30 天内多条信号 → 事件正在发生
    if ctx.signal_count_7d >= 2:
        score = min(100, score + 12)
        reasons.append(f"7 天内 {ctx.signal_count_7d} 条信号（密集）")
    elif ctx.signal_count_30d >= 3:
        score = min(100, score + 8)
        reasons.append(f"30 天内 {ctx.signal_count_30d} 条信号（多次变化）")

    # 3) 采购/招标截止日期（原文明确）
    for sc in ctx.signals:
        if sc.signal.signal_type not in {"PROCUREMENT", "TENDER"}:
            continue
        for evidence in sc.evidences:
            match = _DEADLINE_PATTERN.search(evidence.quoted_text or "")
            if not match:
                continue
            raw = match.group(2)
            normalized = raw.replace("年", "-").replace("月", "-").replace("日", "")
            try:
                deadline = datetime.strptime(normalized, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            days_left = (deadline - now).days
            if 0 <= days_left <= 14:
                score = min(100, score + 15)
                reasons.append(f"采购/招标截止日期在 {days_left} 天内（原文：{match.group(0).strip()[:40]}）")
            elif days_left < 0:
                score = max(0, score - 10)
                reasons.append(f"截止日期已过（{raw}），采购事件可能已结束")
            break

    # 4) 变化类信号（真实版本对比）
    changes = [s for s in ctx.signals if s.signal.change_type]
    if changes:
        score = min(100, score + 8)
        reasons.append(f"存在 {len(changes)} 条真实变化信号（{changes[0].signal.change_type} {changes[0].signal.change_value or ''}）")

    return UrgencyResult(score=max(0, min(score, 100)), reasons=reasons)
