"""T08 Data Growth 报告：summary / gap / quality（全部实时计算，任务书三十九~四十六）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import DATA_GROWTH_TARGETS
from app.models.company import Company, CompanyContact
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.services.validation_readiness import company_readiness


def data_growth_summary(db: Session) -> dict:
    """真实数据增长总览（任务书三十九）。"""
    company_count = db.scalar(select(func.count()).select_from(Company)) or 0
    verified_company_count = db.scalar(select(func.count()).select_from(Company).where(
        Company.verification_status != "UNVERIFIED")) or 0
    type_rows = db.execute(select(Company.organization_type, func.count()).group_by(Company.organization_type)).all()
    source_count = db.scalar(select(func.count()).select_from(Source)) or 0
    source_records = db.scalar(select(func.count()).select_from(SourceRecord)) or 0
    approved_signals = db.scalar(select(func.count()).select_from(Signal).where(Signal.status == "APPROVED")) or 0
    review_signals = db.scalar(select(func.count()).select_from(Signal).where(Signal.status.in_(["VALID", "REVIEW", "DETECTED"]))) or 0
    approved_opportunities = db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.review_status == "APPROVED")) or 0
    review_opportunities = db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.review_status.in_(["PENDING", "NEED_MORE_EVIDENCE"]))) or 0

    # Validation / Contact Ready（逐家真实判定）
    validation_ready = 0
    contact_ready = 0
    for company_id in db.scalars(select(Company.id)).all():
        state = company_readiness(db, company_id)
        if state["validation_ready"]:
            validation_ready += 1
        if state["contact_ready"]:
            contact_ready += 1

    return {
        "company_count": company_count,
        "verified_company_count": verified_company_count,
        "company_type_distribution": {k: v for k, v in type_rows},
        "source_count": source_count,
        "source_records": source_records,
        "approved_signals": approved_signals,
        "review_signals": review_signals,
        "approved_opportunities": approved_opportunities,
        "review_opportunities": review_opportunities,
        "validation_ready_companies": validation_ready,
        "contact_ready_companies": contact_ready,
    }


def data_growth_gap(db: Session) -> dict:
    """缺口报告（任务书四十）：距离各目标还差多少（不足如实报，不硬凑）。"""
    summary = data_growth_summary(db)
    gaps = []
    for key, target in DATA_GROWTH_TARGETS.items():
        field_map = {
            "companies": "company_count",
            "approved_signals": "approved_signals",
            "approved_opportunities": "approved_opportunities",
            "validation_ready": "validation_ready_companies",
        }
        current = summary[field_map[key]]
        gaps.append({
            "target": key,
            "target_count": target,
            "current": current,
            "shortfall": max(0, target - current),
            "progress_pct": round(min(100, current / target * 100), 1) if target else 0,
        })
    return {
        "gaps": gaps,
        "all_targets_met": all(g["shortfall"] == 0 for g in gaps),
        "message": (
            "全部数据目标已达成，可返回 T07 启动第一轮 30 家真实验证"
            if all(g["shortfall"] == 0 for g in gaps)
            else "数据目标未达成：继续多源真实采集，不要硬凑"
        ),
    }


def data_growth_quality(db: Session) -> dict:
    """数据质量 Gate 统计（任务书四十五）：重复率/官网覆盖率/近30天信号覆盖率等。"""
    companies = db.scalars(select(Company)).all()
    total = len(companies)
    normalized_names = [c.normalized_name for c in companies]
    duplicate_count = total - len(set(normalized_names))
    website_covered = sum(1 for c in companies if c.domain or c.website)
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    recent_signal_companies = set(db.scalars(select(Signal.company_id).where(
        Signal.company_id.is_not(None), Signal.collected_at >= cutoff_30d)).all())
    recent_signal_covered = sum(1 for c in companies if c.id in recent_signal_companies)
    avg_quality = round(sum(c.company_data_quality for c in companies) / total, 1) if total else 0
    org_verified = sum(1 for c in companies if c.organization_type != "UNKNOWN")

    # 采集失败率（SourceRecord.parse_status）
    total_records = db.scalar(select(func.count()).select_from(SourceRecord)) or 0
    failed_records = db.scalar(select(func.count()).select_from(SourceRecord).where(SourceRecord.parse_status == "FAILED")) or 0

    return {
        "company_count": total,
        "duplicate_count": duplicate_count,
        "duplicate_rate_pct": round(duplicate_count / total * 100, 1) if total else 0,
        "website_coverage_pct": round(website_covered / total * 100, 1) if total else 0,
        "recent_signal_coverage_pct": round(recent_signal_covered / total * 100, 1) if total else 0,
        "organization_type_resolved_pct": round(org_verified / total * 100, 1) if total else 0,
        "avg_company_data_quality": avg_quality,
        "collection_failure_rate_pct": round(failed_records / total_records * 100, 1) if total_records else 0,
        "stage_gate": {
            "current_stage_target": 30 if total < 100 else (100 if total < 300 else 300),
            "note": "30 → 100 → 300 分阶段扩充；每阶段需人工质检后继续（任务书四十二~四十六）",
        },
    }
