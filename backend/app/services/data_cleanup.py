"""T08.0 数据清理服务：历史污染数据的正式处理（标记，不删除，审计留痕）。

- P0-1/P1-3：平台残留 Company（如"ccgp"）标记 SOURCE_PLATFORM + SUPERSEDED；
- 其误报 Signal 标记 SUPERSEDED（不自动删除，保留审计历史）；
- P0-4：SourceRecord 可靠性快照按当前 Source 刷新（Source A → Record A）；
- P1-2：parse_status 旧值 OK → PARSE_SUCCESS（正文非空）/ PARSE_EMPTY（正文空）；
- 采购主体重关联：ccgp 域名残留记录的 company_id 改指采购单位企业（不改动发现来源）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import is_source_platform_domain
from app.models.company import Company
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.services.audit import write_audit
from app.services.reliability import propagate_record_grade


def _org_type_by_name(name: str) -> str:
    """明确名称规则判断组织类型（不用 LLM）：大学→UNIVERSITY、研究所→RESEARCH_INSTITUTE 等。"""
    if any(k in name for k in ("大学", "学院")):
        return "UNIVERSITY"
    if any(k in name for k in ("研究院", "研究所", "科学院")):
        return "RESEARCH_INSTITUTE"
    if any(k in name for k in ("医院",)):
        return "HOSPITAL"
    if any(k in name for k in ("有限公司", "股份", "集团", "公司")):
        return "COMPANY"
    return "UNKNOWN"


def mark_platform_remnant_companies(db: Session) -> dict:
    """P0-1/P1-3：把因来源平台域名创建的 Company 标记为 SOURCE_PLATFORM + SUPERSEDED。"""
    companies = db.scalars(select(Company)).all()
    marked = []
    for company in companies:
        is_platform = (
            (company.domain and is_source_platform_domain(company.domain))
            or is_source_platform_domain(company.normalized_name)
            or company.company_name in {"ccgp", "www.ccgp.gov.cn", "ccgp.gov.cn"}
            or "ccgp" == company.normalized_name
        )
        if is_platform and company.organization_type != "SOURCE_PLATFORM":
            before = {"organization_type": company.organization_type, "status": company.status}
            company.organization_type = "SOURCE_PLATFORM"
            company.status = "SUPERSEDED"
            write_audit(db, "DATA_QUALITY_FIX", "company", company.id, {
                "fix": "platform_remnant_marked",
                "before": before,
                "after": {"organization_type": "SOURCE_PLATFORM", "status": "SUPERSEDED"},
                "note": "Source Publisher 被误建为业务 Company：标记取代，不删除（审计保留）",
            })
            marked.append(company.id)
    if marked:
        db.commit()
    return {"marked_companies": marked, "count": len(marked)}


def supersede_signals_of_platform_companies(db: Session) -> dict:
    """平台残留 Company 上的误报 Signal 标记 SUPERSEDED（采购公告页挂错主体 + 误判类型）。"""
    platforms = db.scalars(select(Company).where(Company.organization_type == "SOURCE_PLATFORM")).all()
    superseded = []
    for platform in platforms:
        signals = db.scalars(select(Signal).where(
            Signal.company_id == platform.id,
            Signal.status.notin_(["SUPERSEDED", "INVALID"]),
        )).all()
        for signal in signals:
            before = signal.status
            signal.status = "SUPERSEDED"
            signal.payload_json = {**(signal.payload_json or {}),
                                   "t080_superseded_reason": "采购公告页曾误关联平台主体且/或信号类型误判 → 标记取代（历史保留）"}
            write_audit(db, "DATA_QUALITY_FIX", "signal", signal.id, {
                "fix": "platform_signal_superseded", "before": before, "after": "SUPERSEDED",
                "signal_type": signal.signal_type,
            })
            superseded.append(signal.id)
    if superseded:
        db.commit()
    return {"superseded_signals": superseded, "count": len(superseded)}


def reassign_records_to_procurement_subject(db: Session) -> dict:
    """ccgp 公告记录的 company_id 从平台残留改为采购单位企业（页面真实业务主体）。

    仅当记录当前挂在 SOURCE_PLATFORM Company 且能解析出采购人名称时执行；
    采购人企业不存在时创建（PUBLIC_SOURCE_VERIFIED，来源=公告 URL）。
    """
    from app.services.procurement_parser import parse_purchaser

    platforms = db.scalars(select(Company).where(Company.organization_type == "SOURCE_PLATFORM")).all()
    platform_ids = [p.id for p in platforms]
    if not platform_ids:
        return {"reassigned": 0, "created_companies": []}
    records = db.scalars(select(SourceRecord).where(
        SourceRecord.company_id.in_(platform_ids),
        SourceRecord.parse_status == "OK",
    )).all()
    reassigned = 0
    created: list[str] = []
    for record in records:
        purchaser = parse_purchaser(record.raw_text or "")
        if not purchaser:
            continue  # 无法确认采购主体：保持现状，人工处理（不猜测）
        normalized = "".join(purchaser.lower().split())
        company = db.scalar(select(Company).where(Company.normalized_name == normalized))
        if company is None:
            company = Company(
                company_name=purchaser[:300],
                normalized_name=normalized[:300],
                organization_type=_org_type_by_name(purchaser),
                verification_status="PUBLIC_SOURCE_VERIFIED",
                discovery_source_url=record.url,
                verified_at=datetime.now(timezone.utc),
                source_count=0,
            )
            db.add(company)
            db.flush()
            created.append(company.company_name)
            write_audit(db, "CREATE", "company", company.id, {"via": "t08p0_subject_reassign", "name": purchaser})
        if record.company_id != company.id:
            before = record.company_id
            record.company_id = company.id
            record.company_resolve_status = "EXACT"
            write_audit(db, "DATA_QUALITY_FIX", "source_record", record.id, {
                "fix": "subject_reassigned", "before_company_id": before,
                "after_company_id": company.id, "purchaser": purchaser,
            })
            reassigned += 1
    if reassigned or created:
        db.commit()
    return {"reassigned": reassigned, "created_companies": created}


def refresh_record_reliability(db: Session) -> dict:
    """P0-4：SourceRecord 可靠性快照按当前 Source 刷新（Source A → Record A；可降不可升）。"""
    sources = {s.id: s for s in db.scalars(select(Source)).all()}
    records = db.scalars(select(SourceRecord)).all()
    refreshed = 0
    for record in records:
        source = sources.get(record.source_id)
        if source is None:
            continue
        expected = propagate_record_grade(source.reliability_grade)
        if record.source_reliability != expected:
            before = record.source_reliability
            record.source_reliability = expected
            write_audit(db, "DATA_QUALITY_FIX", "source_record", record.id, {
                "fix": "reliability_snapshot_refresh", "before": before,
                "after": expected, "source_grade": source.reliability_grade,
            })
            refreshed += 1
    if refreshed:
        db.commit()
    return {"refreshed_records": refreshed}


def fix_parse_status(db: Session) -> dict:
    """P1-2：旧 parse_status 值迁移 —— OK→PARSE_SUCCESS/PARSE_EMPTY（正文空不得算解析成功）。"""
    rows = db.scalars(select(SourceRecord).where(SourceRecord.parse_status.in_(["OK", ""]))).all()
    fixed = 0
    for record in rows:
        has_text = bool((record.raw_text or "").strip()) or bool((record.title or "").strip())
        new_status = "PARSE_SUCCESS" if has_text else "PARSE_EMPTY"
        if record.parse_status != new_status:
            before = record.parse_status
            record.parse_status = new_status
            write_audit(db, "DATA_QUALITY_FIX", "source_record", record.id, {
                "fix": "parse_status_normalized", "before": before, "after": new_status,
            })
            fixed += 1
    if fixed:
        db.commit()
    return {"fixed": fixed}


def backfill_published_at(db: Session) -> dict:
    """P0-5 历史修复：published_at 为空的采购公告记录，从正文结构化字段回填公告时间。"""
    from app.services.procurement_parser import parse_announcement_time

    records = db.scalars(select(SourceRecord).where(SourceRecord.published_at.is_(None))).all()
    backfilled = 0
    for record in records:
        if "ccgp.gov.cn" not in (record.url or ""):
            continue
        announcement = parse_announcement_time(record.raw_text or "")
        if announcement is None:
            record.metadata_json = {**(record.metadata_json or {}), "freshness_source": "COLLECTED_AT_FALLBACK"}
            continue
        record.published_at = announcement
        record.metadata_json = {**(record.metadata_json or {}), "freshness_source": "ANNOUNCEMENT_TIME"}
        write_audit(db, "DATA_QUALITY_FIX", "source_record", record.id, {
            "fix": "published_at_backfill", "after": announcement.isoformat(),
        })
        backfilled += 1
    if backfilled:
        db.commit()
    return {"backfilled": backfilled}


def run_all_fixes(db: Session) -> dict:
    """按依赖顺序执行全部修复（P0-1 → 重关联 → 信号取代 → P0-4 → P1-2 → P0-5 回填）。"""
    return {
        "platform_companies": mark_platform_remnant_companies(db),
        "subject_reassignment": reassign_records_to_procurement_subject(db),
        "platform_signals": supersede_signals_of_platform_companies(db),
        "reliability_refresh": refresh_record_reliability(db),
        "parse_status": fix_parse_status(db),
        "published_at_backfill": backfill_published_at(db),
    }
