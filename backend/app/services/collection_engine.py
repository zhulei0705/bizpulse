"""采集引擎（T03）：Adapter 产物 → 版本化 SourceRecord → 企业关联。

统一入库规则（所有采集入口共用，不允许两套逻辑）：
- 同 source + canonical_url 的最新记录 content_hash 相同 → 不创建业务数据，
  仅更新 checked_at（记 SKIPPED_UNCHANGED）；
- content_hash 变化 → 旧版本 is_latest=False 保留，新版本挂 parent_record_id
  与递增 version_number（记 UPDATED / 版本历史可追溯）；
- 新 URL → 创建（记 CREATED）；
- parse_status=FAILED → 保存失败记录留痕（不生成假正文），计 error。

Signal 生成保持 T02 行为（仅对真实文本规则提取，逐条关联 source_record）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import CollectedItem, CollectorAdapter
from app.models.company import Company
from app.models.job import CollectionJob
from app.models.source import Source, SourceRecord
from app.services.audit import write_audit
from app.services.company_resolver import resolve_record_company
from app.services.ingest import create_rule_signals, resolve_or_create_company  # 复用 T02 规则信号
from app.services import extractor

logger = logging.getLogger(__name__)


def _detect_language(text: str) -> str | None:
    cjk = sum(1 for ch in text[:2000] if "\u4e00" <= ch <= "\u9fff")
    if cjk > 100:
        return "zh"
    if text and sum(ch.isalpha() for ch in text[:2000]) > 100:
        return "en"
    return None


def _parse_published(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def persist_collected(db: Session, source: Source, item: CollectedItem, *, extract_signals: bool = True) -> tuple[SourceRecord, str]:
    """入库一条采集结果，返回 (record, outcome)。outcome: CREATED / UPDATED_VERSION / SKIPPED_UNCHANGED / FAILED。"""
    fingerprint = item.content_hash()
    canonical = item.canonical_url or item.url

    latest = db.scalar(
        select(SourceRecord).where(
            SourceRecord.source_id == source.id,
            SourceRecord.canonical_url == canonical,
            SourceRecord.is_latest.is_(True),
        )
    )

    if latest and latest.content_hash == fingerprint and item.parse_status == "OK":
        latest.checked_at = datetime.now(timezone.utc)
        return latest, "SKIPPED_UNCHANGED"

    organization = item.extra.get("organization") or item.extra.get("og_site_name")
    new_record = SourceRecord(
        source_id=source.id,
        url=item.url,
        canonical_url=canonical,
        title=item.title,
        raw_text=item.raw_text,
        raw_html_path=item.extra.get("raw_html_path"),
        published_at=_parse_published(item.published_at),
        content_hash=fingerprint,
        http_status=item.http_status,
        content_type=item.content_type,
        language=item.language or _detect_language(item.raw_text or ""),
        source_reliability=source.reliability_grade,
        parse_status=item.parse_status,
        error_message=item.error_message,
        checked_at=datetime.now(timezone.utc),
        metadata_json={"collected_via": source.collector_type or "web_page", "author": item.author, **{k: v for k, v in item.extra.items() if k not in {"raw_html_path", "organization", "og_site_name"}}},
    )
    if latest is not None:
        new_record.parent_record_id = latest.id
        new_record.version_number = (latest.version_number or 1) + 1
        new_record.company_id = latest.company_id  # 版本延续既有关联
        new_record.company_resolve_status = latest.company_resolve_status
        latest.is_latest = False
    db.add(new_record)
    db.flush()

    outcome = "FAILED" if item.parse_status == "FAILED" else ("UPDATED_VERSION" if latest is not None else "CREATED")

    # 企业关联（仅新记录；版本记录沿用父版本关联）
    if outcome == "CREATED":
        record, result = resolve_record_company(db, new_record, organization)
        if result.status in {"EXACT", "HIGH_CONFIDENCE"} and record.company_id:
            company = db.get(Company, record.company_id)
            if company:
                company.source_count = (company.source_count or 0) + 1
        elif item.parse_status == "OK":
            # Resolver 未给出自动关联时，回退 T02 的「官方域名/名称建档」能力（同样基于域名与明确名称，不猜）
            page_like = extractor.FetchedItemAdapter(item)
            company = resolve_or_create_company(db, extractor.identify_company(page_like), page_like)
            if company:
                new_record.company_id = company.id
                new_record.company_resolve_status = "HIGH_CONFIDENCE"

    write_audit(db, "COLLECT_RECORD", "source_record", new_record.id, {
        "source_id": source.id, "url": item.url, "outcome": outcome,
        "version": new_record.version_number, "parse_status": item.parse_status,
    })

    # Signal 提取（保守：仅对真实正文规则提取；每条 Signal 关联 source_record）
    if extract_signals and outcome in {"CREATED", "UPDATED_VERSION"} and item.raw_text and new_record.company_id:
        page_like = extractor.FetchedItemAdapter(item)
        create_rule_signals(db, db.get(Company, new_record.company_id), new_record, page_like)

    return new_record, outcome


def run_collection_job(db: Session, job: CollectionJob, adapter: CollectorAdapter) -> CollectionJob:
    """执行采集 Job：统一状态机（PENDING→RUNNING→SUCCESS/PARTIAL_SUCCESS/FAILED）+ 逐 URL 日志 + 明细统计。"""
    started = datetime.now(timezone.utc)
    job.status = "RUNNING"
    job.started_at = started
    db.commit()

    counts = {"found": 0, "created": 0, "updated": 0, "skipped": 0, "failed": 0}
    source = db.get(Source, job.source_id) if job.source_id else None
    try:
        items = adapter.build_records()
        for idx, item in enumerate(items, start=1):
            counts["found"] += 1
            if source is None:
                continue
            _, outcome = persist_collected(db, source, item)
            if outcome == "CREATED":
                counts["created"] += 1
            elif outcome == "UPDATED_VERSION":
                counts["updated"] += 1
            elif outcome == "SKIPPED_UNCHANGED":
                counts["skipped"] += 1
            else:
                counts["failed"] += 1
            job.progress = int(idx / max(len(items), 1) * 100)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job.status = "FAILED"
        job.error_count += 1
        job.error_message = str(exc)[:2000]
        job.finished_at = datetime.now(timezone.utc)
        job.duration_seconds = (job.finished_at - started).total_seconds()
        job.run_log_json = adapter.run_log
        db.commit()
        if source is not None:
            source.last_run_at = job.finished_at
            db.commit()
        raise

    job.finished_at = datetime.now(timezone.utc)
    job.duration_seconds = (job.finished_at - started).total_seconds()
    job.items_found = counts["found"]
    job.items_created = counts["created"]
    job.items_updated = counts["updated"]
    job.items_skipped = counts["skipped"]
    job.error_count = counts["failed"]
    job.record_count = counts["created"] + counts["updated"]
    job.run_log_json = adapter.run_log
    job.status = "FAILED" if (counts["failed"] > 0 and counts["created"] + counts["updated"] == 0 and counts["found"] > 0) else (
        "PARTIAL_SUCCESS" if counts["failed"] > 0 else "SUCCESS"
    )
    if source is not None:
        source.last_run_at = job.finished_at
        if job.status in {"SUCCESS", "PARTIAL_SUCCESS"}:
            source.last_success_at = job.finished_at
    db.commit()
    db.refresh(job)
    return job
