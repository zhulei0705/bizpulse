"""T08 Source Yield / Source Health（全部实时从正式库计算，任务书三十六~三十八）。

Yield 回答"哪个数据源真的有价值"：每个 Source 的采集记录 → Signal → Approved → Opportunity 链路。
Health 回答"数据源是否健康"：成功率/最近成功/近 7、30 天记录/429/403/解析失败。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.job import CollectionJob
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.source import Source, SourceRecord


def _aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def source_yield(db: Session) -> list[dict]:
    """每个 Source 的产出链路统计（按真实外键关系聚合）。"""
    sources = db.scalars(select(Source)).all()
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    rows: list[dict] = []
    for source in sources:
        record_ids = db.scalars(select(SourceRecord.id).where(SourceRecord.source_id == source.id)).all()
        record_count = len(record_ids)
        record_count_7d = db.scalar(select(func.count()).select_from(SourceRecord).where(
            SourceRecord.source_id == source.id, SourceRecord.collected_at >= cutoff_7d)) or 0
        record_count_30d = db.scalar(select(func.count()).select_from(SourceRecord).where(
            SourceRecord.source_id == source.id, SourceRecord.collected_at >= cutoff_30d)) or 0

        signal_count = 0
        approved_signal_count = 0
        if record_ids:
            signal_count = db.scalar(select(func.count()).select_from(Signal).where(
                Signal.source_record_id.in_(record_ids))) or 0
            approved_signal_count = db.scalar(select(func.count()).select_from(Signal).where(
                Signal.source_record_id.in_(record_ids), Signal.status == "APPROVED")) or 0

        opportunity_count = 0
        approved_opportunity_count = 0
        if approved_signal_count:
            company_ids = db.scalars(select(SourceRecord.company_id).where(
                SourceRecord.source_id == source.id, SourceRecord.company_id.is_not(None))).all()
            if company_ids:
                opportunity_count = db.scalar(select(func.count()).select_from(Opportunity).where(
                    Opportunity.company_id.in_(company_ids))) or 0
                approved_opportunity_count = db.scalar(select(func.count()).select_from(Opportunity).where(
                    Opportunity.company_id.in_(company_ids), Opportunity.review_status == "APPROVED")) or 0

        rows.append({
            "source_id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "reliability_grade": source.reliability_grade,
            "enabled": source.enabled,
            "record_count": record_count,
            "records_7d": record_count_7d,
            "records_30d": record_count_30d,
            "signal_count": signal_count,
            "approved_signal_count": approved_signal_count,
            "opportunity_count": opportunity_count,
            "approved_opportunity_count": approved_opportunity_count,
        })
    rows.sort(key=lambda x: (-x["approved_signal_count"], -x["record_count"]))
    return rows


def source_health(db: Session) -> list[dict]:
    """每个 Source 的健康状态（从 CollectionJob.run_log 聚合；无假数据）。"""
    sources = db.scalars(select(Source)).all()
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    rows: list[dict] = []
    for source in sources:
        jobs = db.scalars(select(CollectionJob).where(CollectionJob.name.like(f"%{source.name}%")).order_by(CollectionJob.created_at.desc()).limit(20)).all()
        total_urls = 0
        ok_urls = 0
        count_429 = 0
        count_403 = 0
        parse_failures = 0
        for job in jobs:
            for entry in (job.run_log_json or []):
                status = str(entry.get("status", ""))
                total_urls += 1
                if status.startswith("OK"):
                    ok_urls += 1
                if "429" in status:
                    count_429 += 1
                if "403" in status:
                    count_403 += 1
                if status == "FAILED" or entry.get("error"):
                    parse_failures += 1
        rows.append({
            "source_id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "collector_type": source.collector_type,
            "enabled": source.enabled,
            "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
            "success_rate": source.success_rate,
            "jobs_sampled": len(jobs),
            "url_attempts": total_urls,
            "url_ok": ok_urls,
            "count_429": count_429,
            "count_403": count_403,
            "parse_failure_count": parse_failures,
            "records_7d": db.scalar(select(func.count()).select_from(SourceRecord).where(
                SourceRecord.source_id == source.id, SourceRecord.collected_at >= cutoff_7d)) or 0,
            "records_30d": db.scalar(select(func.count()).select_from(SourceRecord).where(
                SourceRecord.source_id == source.id, SourceRecord.collected_at >= cutoff_30d)) or 0,
        })
    return rows
