from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import VALIDATING_STAGES
from app.models.company import Company
from app.models.job import CollectionJob
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.source import Source, SourceRecord


def start_of_utc_day() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def _signal_trend(db: Session, days: int = 14) -> list[dict]:
    """最近 N 天每日新增商业信号（真实按天统计，缺失日补 0）。"""
    start = start_of_utc_day() - timedelta(days=days - 1)
    rows = db.execute(
        select(func.date(Signal.collected_at).label("d"), func.count())
        .where(Signal.collected_at >= start)
        .group_by("d")
    ).all()
    by_day = {str(d): c for d, c in rows}
    trend = []
    for i in range(days):
        day = start + timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        trend.append({"date": day.strftime("%m-%d"), "count": by_day.get(key, 0)})
    return trend


def _companies_to_watch(db: Session, limit: int = 5) -> list[dict]:
    """今日值得关注的企业：按最近真实信号时间排序的真实企业（无虚构）。"""
    recent = db.scalars(
        select(Signal).where(Signal.company_id.is_not(None)).order_by(Signal.collected_at.desc()).limit(60)
    ).all()
    seen: dict[str, Signal] = {}
    for s in recent:
        seen.setdefault(s.company_id, s)  # 保留每个企业最新一条
    result = []
    for company_id, latest in list(seen.items())[:limit]:
        company = db.get(Company, company_id)
        if not company:
            continue
        top_opp = db.scalar(
            select(Opportunity).where(Opportunity.company_id == company_id, Opportunity.status == "ACTIVE").order_by(Opportunity.total_score.desc())
        )
        result.append({
            "company_id": company_id,
            "company_name": company.company_name,
            "industry": company.industry,
            "latest_signal_type": latest.signal_type,
            "latest_signal_title": latest.title,
            "opportunity_level": top_opp.grade if top_opp else company.opportunity_level,
            "top_opportunity_score": round(top_opp.total_score, 1) if top_opp else None,
            "evidence_count": _count(db, select(func.count()).select_from(SourceRecord).where(SourceRecord.company_id == company_id)),
            "signal_count": _count(db, select(func.count()).select_from(Signal).where(Signal.company_id == company_id)),
            "updated_at": company.updated_at.isoformat(),
        })
    return result


def dashboard_summary(db: Session) -> dict:
    today = start_of_utc_day()
    recent_signals = db.scalars(select(Signal).order_by(Signal.collected_at.desc()).limit(5)).all()
    recent = []
    for s in recent_signals:
        company_name = db.scalar(select(Company.company_name).where(Company.id == s.company_id)) if s.company_id else None
        record = db.get(SourceRecord, s.source_record_id)
        source = db.get(Source, record.source_id) if record else None
        recent.append({
            "id": s.id,
            "company_id": s.company_id,
            "company_name": company_name,
            "signal_type": s.signal_type,
            "title": s.title,
            "confidence": s.confidence,
            "collected_at": s.collected_at.isoformat(),
            "fact_or_inference": s.fact_or_inference,
            "verification_status": s.verification_status,
            "reliability_grade": source.reliability_grade if source else None,
            "url": record.url if record else None,
        })
    total_records = _count(db, select(func.count()).select_from(SourceRecord))
    verified_records = _count(db, select(func.count()).select_from(SourceRecord).where(SourceRecord.verification_status == "VERIFIED"))
    from app.llm import llm_configured as _llm_configured
    return {
        # 总量统计（真实数据，无数据时为 0）
        "company_count": _count(db, select(func.count()).select_from(Company)),
        "signal_count": _count(db, select(func.count()).select_from(Signal)),
        "opportunity_count": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.status == "ACTIVE")),
        "grade_a_or_higher": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.grade.in_(["A", "S"]), Opportunity.status == "ACTIVE")),
        "pending_review": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(["NEW", "REVIEW"]), Opportunity.status == "ACTIVE")),
        "validating": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(VALIDATING_STAGES), Opportunity.status == "ACTIVE")),
        "won": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.stage == "WON")),
        "rejected": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.stage == "REJECTED")),
        "active_sources": _count(db, select(func.count()).select_from(Source).where(Source.enabled.is_(True))),
        "running_jobs": _count(db, select(func.count()).select_from(CollectionJob).where(CollectionJob.status == "RUNNING")),
        # 今日增量
        "today_new_companies": _count(db, select(func.count()).select_from(Company).where(Company.created_at >= today)),
        "today_new_signals": _count(db, select(func.count()).select_from(Signal).where(Signal.collected_at >= today)),
        "today_new_opportunities": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.created_at >= today)),
        # 数据可信指数（已人工验证的来源记录占比，0-100；无记录时为 0）
        "total_records": total_records,
        "verified_records": verified_records,
        "llm_configured": _llm_configured(),
        # 真实趋势与榜单
        "signal_trend": _signal_trend(db, days=30),
        "recent_signals": recent,
        "companies_to_watch": _companies_to_watch(db),
        "top_markets": [],
    }
