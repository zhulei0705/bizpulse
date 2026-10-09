"""OpportunityDeduplicator —— 机会去重（T05）。

fingerprint = sha256(company_id + pain_category + solution_category + 时间窗桶)
- 同指纹的"活跃"候选在窗口内只保留一条：更新（合并新 Signal、刷新分数），不新建；
- analysis_input_hash = sha256(company + signal ids + signal fingerprints + prompt_version)
  输入完全相同则跳过重复分析（不每天重复分析相同内容）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.opportunity_candidate import OpportunityCandidate

_ACTIVE_CANDIDATE_STATUSES = ("DETECTED", "NEED_MORE_EVIDENCE", "REVIEW")
# 终态候选：人工已处理（approve=CONVERTED / reject=REJECTED / APPROVED），fingerprint 全局唯一，
# 重新分析不得重建同指纹候选（否则 UNIQUE 冲突且覆盖人工决策）。
_FINALIZED_CANDIDATE_STATUSES = ("CONVERTED", "APPROVED", "REJECTED")


def compute_candidate_fingerprint(
    company_id: str,
    pain_category: str | None,
    solution_category: str | None,
    published_at: datetime | None = None,
    collected_at: datetime | None = None,
    *,
    window_days: int | None = None,
) -> str:
    window = window_days or settings.opportunity_dedup_window_days
    anchor = published_at or collected_at or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    bucket_index = anchor.replace(hour=0, minute=0, second=0, microsecond=0).toordinal() // max(window, 1)
    payload = json.dumps([company_id, pain_category or "-", solution_category or "-", str(bucket_index)],
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_active_candidate(db: Session, fingerprint: str) -> OpportunityCandidate | None:
    """查找同指纹的活跃候选（窗口内）。"""
    candidates = db.scalars(
        select(OpportunityCandidate).where(
            OpportunityCandidate.fingerprint == fingerprint,
            OpportunityCandidate.status.in_(_ACTIVE_CANDIDATE_STATUSES),
        ).order_by(OpportunityCandidate.updated_at.desc())
    ).all()
    window = settings.opportunity_dedup_window_days
    now = datetime.now(timezone.utc)
    for candidate in candidates:
        anchor = candidate.updated_at or candidate.created_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if now - anchor <= timedelta(days=window):
            return candidate
    return None


def find_finalized_candidate(db: Session, fingerprint: str) -> OpportunityCandidate | None:
    """同指纹的已终态候选（CONVERTED/APPROVED/REJECTED）。

    fingerprint 有全局唯一约束：活跃候选查不到时若存在终态候选，直接 INSERT 会撞
    UNIQUE（真实数据 force 重分析时发现）。终态候选代表人工决策已完成，应跳过重建。
    """
    return db.scalar(
        select(OpportunityCandidate).where(
            OpportunityCandidate.fingerprint == fingerprint,
            OpportunityCandidate.status.in_(_FINALIZED_CANDIDATE_STATUSES),
        ).order_by(OpportunityCandidate.updated_at.desc()).limit(1)
    )


def compute_analysis_input_hash(
    company_id: str,
    signal_ids: list[str],
    signal_fingerprints: list[str],
    prompt_version: str,
) -> str:
    payload = json.dumps({
        "company_id": company_id,
        "signal_ids": sorted(signal_ids),
        "signal_fingerprints": sorted(signal_fingerprints),
        "prompt_version": prompt_version,
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_latest_candidate_with_hash(db: Session, company_id: str, input_hash: str) -> OpportunityCandidate | None:
    """最近一条同输入 hash 的候选（用于跳过完全相同的重复分析）。"""
    return db.scalar(
        select(OpportunityCandidate).where(
            OpportunityCandidate.company_id == company_id,
            OpportunityCandidate.analysis_input_hash == input_hash,
        ).order_by(OpportunityCandidate.created_at.desc()).limit(1)
    )
