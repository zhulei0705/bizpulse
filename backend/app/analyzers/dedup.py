"""SignalDeduplicator —— 指纹去重与多来源合并（T04）。

fingerprint = sha256(company_id + signal_type + normalized(核心事件) + 日期窗口)
- 同 fingerprint 且在 dedup_window_days 内 → 不新建 Signal，向既有 Signal 追加
  新来源的 SignalEvidence（多来源合并，提升证据强度）并更新 last_seen_at；
- 超出时间窗口视为新事件（同一事件不会被永久合并）。
窗口与事件文本归一化规则均配置化。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.signal import Signal, SignalEvidence


def normalize_event_text(text: str) -> str:
    """事件核心文本归一：去空白/标点/数字量词差异，保留语义主体。"""
    text = re.sub(r"[\s，。、；：,.;:！!？?\"'“”‘’（）()\[\]【】<>《》-]+", "", text or "")
    text = re.sub(r"\d+", "#", text)
    return text.lower()[:200]


def event_time_bucket(published_at: datetime | None, collected_at: datetime | None, window_days: int) -> str:
    """日期窗口分桶：同事件在窗口内落同桶（避免永久合并）。"""
    anchor = published_at or collected_at or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    bucket = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
    # 以窗口起点为桶（取整到 window 天）
    days_since_epoch = bucket.toordinal()
    bucket_index = days_since_epoch // max(window_days, 1)
    return str(bucket_index)


def compute_signal_fingerprint(company_id: str | None, signal_type: str, event_text: str, published_at: datetime | None, collected_at: datetime | None = None) -> str:
    window = settings.signal_dedup_window_days
    payload = json.dumps([
        company_id or "-",
        signal_type,
        normalize_event_text(event_text),
        event_time_bucket(published_at, collected_at, window),
    ], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_duplicate_signal(db: Session, fingerprint: str, *, within_days: int | None = None) -> Signal | None:
    """查找同指纹且未失效、仍在窗口内的既有正式 Signal。"""
    candidates = db.scalars(
        select(Signal).where(Signal.signal_fingerprint == fingerprint, Signal.status.in_(["REVIEW", "APPROVED", "VALID", "CANDIDATE"]))
    ).all()
    window = within_days or settings.signal_dedup_window_days
    now = datetime.now(timezone.utc)
    for signal in candidates:
        anchor = signal.last_seen_at or signal.first_seen_at or signal.created_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if now - anchor <= timedelta(days=window):
            return signal
    return None


def merge_evidence(db: Session, signal: Signal, *, source_record_id: str, quoted_text: str, start_offset: int | None, end_offset: int | None, confidence: int) -> bool:
    """多来源合并：向既有 Signal 追加新来源证据（同记录去重）；返回是否发生合并。"""
    existing = db.scalar(
        select(SignalEvidence).where(
            SignalEvidence.signal_id == signal.id,
            SignalEvidence.source_record_id == source_record_id,
        )
    )
    if existing:
        return False
    db.add(SignalEvidence(
        signal_id=signal.id,
        source_record_id=source_record_id,
        quoted_text=(quoted_text or "")[:2000],
        start_offset=start_offset,
        end_offset=end_offset,
        confidence=confidence,
    ))
    signal.last_seen_at = datetime.now(timezone.utc)
    signal.created_by = "MERGE"
    # 多来源确认 → 适度提升置信度（可解释：证据相互印证）
    signal.confidence = min(100, signal.confidence + 4)
    return True
