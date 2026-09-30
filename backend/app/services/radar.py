"""机会雷达服务（UI02）：Router → Service → Database 分层。

所有聚合来自真实数据库；空库返回空数组与真实 0，禁止 Demo 数据。
筛选参数（industry/grade/min_score/min_evidence/signal_type/time range）
直接作用于 SQL 查询，禁止只在前端过滤。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.models.signal import Signal
from app.services.dashboard import _count, start_of_utc_day


@dataclass(frozen=True)
class RadarFilters:
    industry: str | None = None
    country: str | None = None
    grade: str | None = None
    min_score: float | None = None
    min_evidence: int | None = None
    min_evidence_score: int | None = None
    signal_type: str | None = None
    days: int | None = None  # 时间范围：最近 N 天

    def opp_filters(self):
        """作用于 Opportunity 的公共过滤（关联企业行业/国家）。"""
        filters = [Opportunity.status == "ACTIVE"]
        if self.industry:
            filters.append(Company.industry == self.industry)
        if self.country:
            filters.append(Company.country == self.country)
        if self.grade:
            filters.append(Opportunity.grade == self.grade)
        if self.min_score is not None:
            filters.append(Opportunity.total_score >= self.min_score)
        if self.min_evidence_score is not None:
            filters.append(Opportunity.evidence_score >= self.min_evidence_score)
        return filters


def _opp_join(filters):
    return (
        select(Opportunity)
        .join(Company, Opportunity.company_id == Company.id)
        .where(*filters)
    )


def _evidence_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(OpportunityEvidence.opportunity_id, func.count()).group_by(OpportunityEvidence.opportunity_id)
    ).all()
    return {oid: c for oid, c in rows}


def _serialize_opportunity(opportunity: Opportunity, company_name: str | None, evidence_count: int, latest_signal_title: str | None) -> dict:
    return {
        "id": opportunity.id,
        "company_id": opportunity.company_id,
        "company_name": company_name,
        "title": opportunity.title,
        "problem": opportunity.problem,
        "solution": opportunity.solution,
        "value_proposition": opportunity.value_proposition,
        "trigger_event": opportunity.trigger_event,
        "purchase_intent": opportunity.purchase_intent,
        "pain_score": opportunity.pain_score,
        "budget_score": opportunity.budget_score,
        "intent_score": opportunity.intent_score,
        "urgency_score": opportunity.urgency_score,
        "agent_fit_score": opportunity.agent_fit_score,
        "reachability_score": opportunity.reachability_score,
        "evidence_score": opportunity.evidence_score,
        "total_score": round(opportunity.total_score, 1),
        "grade": opportunity.grade,
        "stage": opportunity.stage,
        "review_status": opportunity.review_status,
        "review_note": opportunity.review_note,
        "reviewed_at": opportunity.reviewed_at.isoformat() if opportunity.reviewed_at else None,
        "evidence_count": evidence_count,
        "latest_signal_title": latest_signal_title,
        "created_at": opportunity.created_at.isoformat(),
        "updated_at": opportunity.updated_at.isoformat(),
    }


def _latest_signal_titles(db: Session) -> dict[str, str]:
    """每个机会主信号的标题（触发事件追溯）。"""
    rows = db.execute(
        select(Opportunity.id, Signal.title)
        .join(Signal, Opportunity.primary_signal_id == Signal.id)
    ).all()
    return {oid: title for oid, title in rows}


def _metrics(db: Session, filters: RadarFilters) -> dict:
    today = start_of_utc_day()
    high_value_stmt = select(func.count()).select_from(
        _opp_join(filters.opp_filters()).where(Opportunity.grade.in_(["A", "S"])).subquery()
    )
    return {
        "today_signals": _count(db, select(func.count()).select_from(Signal).where(Signal.collected_at >= today)),
        "today_opportunities": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.created_at >= today, Opportunity.status == "ACTIVE")),
        "high_value_opportunities": _count(db, high_value_stmt),
        "grade_a_or_higher": _count(db, high_value_stmt),
        "pending_reviews": _count(db, select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(["NEW", "REVIEW"]), Opportunity.status == "ACTIVE")),
        "potential_opportunities": _count(db, select(func.count()).select_from(_opp_join(filters.opp_filters()).subquery())),
    }


def _locations(db: Session, filters: RadarFilters) -> list[dict]:
    """真实地理机会点：仅当企业具有真实 country/province/city 时返回；无地理数据返回空数组（禁止猜测坐标）。"""
    filters_sql = filters.opp_filters()
    rows = db.scalars(_opp_join(filters_sql).order_by(Opportunity.total_score.desc()).limit(50)).all()
    names = dict(db.execute(select(Company.id, Company.company_name)).all())
    geo_rows = db.execute(select(Company.id, Company.country, Company.province, Company.city)).all()
    geos = {row[0]: (row[1], row[2], row[3]) for row in geo_rows}
    locations = []
    for opp in rows:
        geo = geos.get(opp.company_id)
        if not geo or not (geo[0] or geo[1] or geo[2]):
            continue  # 无真实地理信息的企业不进地图层
        locations.append({
            "company_id": opp.company_id,
            "company_name": names.get(opp.company_id),
            "country": geo[0],
            "province": geo[1],
            "city": geo[2],
            "opportunity_count": 1,
            "top_score": round(opp.total_score, 1),
            "top_grade": opp.grade,
        })
    # 同企业合并
    merged: dict[str, dict] = {}
    for loc in locations:
        key = loc["company_id"]
        if key in merged:
            merged[key]["opportunity_count"] += 1
            if loc["top_score"] > merged[key]["top_score"]:
                merged[key]["top_score"] = loc["top_score"]
                merged[key]["top_grade"] = loc["top_grade"]
        else:
            merged[key] = loc
    return list(merged.values())[:20]


def _latest_signals(db: Session, filters: RadarFilters, limit: int = 20) -> list[dict]:
    from app.models.source import Source, SourceRecord

    sig_filters = []
    if filters.signal_type:
        sig_filters.append(Signal.signal_type == filters.signal_type)
    if filters.industry or filters.country:
        sub = select(Company.id).where(*([c for c in [Company.industry == filters.industry if filters.industry else None, Company.country == filters.country if filters.country else None] if c is not None]))
        sig_filters.append(Signal.company_id.in_(sub))
    if filters.days:
        from datetime import timedelta
        sig_filters.append(Signal.collected_at >= start_of_utc_day() - timedelta(days=filters.days - 1))
    signals = db.scalars(
        select(Signal).where(*sig_filters).order_by(Signal.collected_at.desc()).limit(limit)
    ).all()
    names = dict(db.execute(select(Company.id, Company.company_name)).all())
    # 每个企业最高 ACTIVE 机会总分（机会流条目的 Opportunity Score 展示；无机会为 None）
    top_scores: dict[str, float] = {}
    for company_id, score in db.execute(
        select(Opportunity.company_id, func.max(Opportunity.total_score))
        .where(Opportunity.status == "ACTIVE").group_by(Opportunity.company_id)
    ).all():
        top_scores[company_id] = round(float(score), 1)
    result = []
    for s in signals:
        record = db.get(SourceRecord, s.source_record_id)
        source = db.get(Source, record.source_id) if record else None
        result.append({
            "id": s.id,
            "company_id": s.company_id,
            "company_name": names.get(s.company_id) if s.company_id else None,
            "signal_type": s.signal_type,
            "title": s.title,
            "confidence": s.confidence,
            "collected_at": s.collected_at.isoformat(),
            "fact_or_inference": s.fact_or_inference,
            "verification_status": s.verification_status,
            "reliability_grade": source.reliability_grade if source else None,
            "evidence_count": 1 if record else 0,
            "url": record.url if record else None,
            "opportunity_score": top_scores.get(s.company_id) if s.company_id else None,
        })
    return result


def _top_opportunities(db: Session, filters: RadarFilters, limit: int = 10) -> list[dict]:
    rows = db.scalars(
        _opp_join(filters.opp_filters()).order_by(Opportunity.total_score.desc(), Opportunity.updated_at.desc()).limit(limit * 3)
    ).all()
    ev_counts = _evidence_counts(db)
    titles = _latest_signal_titles(db)
    names = dict(db.execute(select(Company.id, Company.company_name)).all())
    items = []
    for opp in rows:
        ev_count = ev_counts.get(opp.id, 0)
        if filters.min_evidence is not None and ev_count < filters.min_evidence:
            continue
        items.append(_serialize_opportunity(opp, names.get(opp.company_id), ev_count, titles.get(opp.id)))
        if len(items) >= limit:
            break
    return items


def _industry_heat(db: Session, limit: int = 10) -> list[dict]:
    """真实行业聚合：企业带 industry 才统计；无行业数据返回空数组。"""
    rows = db.execute(select(Company.id, Company.industry).where(Company.industry.is_not(None))).all()
    if not rows:
        return []
    by_industry: dict[str, list[str]] = {}
    for company_id, industry in rows:
        by_industry.setdefault(industry, []).append(company_id)
    heat = []
    for industry, company_ids in by_industry.items():
        opps = db.scalars(
            select(Opportunity).where(Opportunity.company_id.in_(company_ids), Opportunity.status == "ACTIVE")
        ).all()
        signal_count = _count(db, select(func.count()).select_from(Signal).where(Signal.company_id.in_(company_ids)))
        heat.append({
            "industry": industry,
            "company_count": len(company_ids),
            "signal_count": signal_count,
            "opportunity_count": len(opps),
            "average_score": round(sum(o.total_score for o in opps) / len(opps), 1) if opps else 0,
        })
    heat.sort(key=lambda x: (x["opportunity_count"], x["signal_count"], x["company_count"]), reverse=True)
    return heat[:limit]


def _grade_distribution(db: Session, filters: RadarFilters) -> list[dict]:
    rows = db.execute(
        select(Opportunity.grade, func.count())
        .join(Company, Opportunity.company_id == Company.id)
        .where(*filters.opp_filters())
        .group_by(Opportunity.grade)
    ).all()
    counts = {g: c for g, c in rows}
    return [{"grade": g, "count": counts.get(g, 0)} for g in ["S", "A", "B", "C", "D"]]


def _pending_reviews(db: Session, limit: int = 10) -> list[dict]:
    """待人工审核（NEW / REVIEW 阶段）的真实机会。"""
    rows = db.scalars(
        select(Opportunity).where(Opportunity.stage.in_(["NEW", "REVIEW"]), Opportunity.status == "ACTIVE").order_by(Opportunity.total_score.desc()).limit(limit)
    ).all()
    ev_counts = _evidence_counts(db)
    titles = _latest_signal_titles(db)
    names = dict(db.execute(select(Company.id, Company.company_name)).all())
    return [_serialize_opportunity(o, names.get(o.company_id), ev_counts.get(o.id, 0), titles.get(o.id)) for o in rows]


def _score_distribution(db: Session, filters: RadarFilters) -> list[dict]:
    """机会总分区间分布（0-20/21-40/41-60/61-80/81-100），全部真实计数。"""
    rows = db.execute(
        select(Opportunity.total_score)
        .join(Company, Opportunity.company_id == Company.id)
        .where(*filters.opp_filters())
    ).all()
    buckets = [
        {"range": "0-20", "label": "0~20", "count": 0},
        {"range": "21-40", "label": "21~40", "count": 0},
        {"range": "41-60", "label": "41~60", "count": 0},
        {"range": "61-80", "label": "61~80", "count": 0},
        {"range": "81-100", "label": "81~100", "count": 0},
    ]
    for (score,) in rows:
        s = float(score)
        idx = 4 if s >= 81 else (3 if s >= 61 else (2 if s >= 41 else (1 if s >= 21 else 0)))
        buckets[idx]["count"] += 1
    return buckets


# 来源类型 → 展示分类（真实 source_type 映射；数据库没有的类型不显示）
SOURCE_CATEGORY: dict[str, str] = {
    "OFFICIAL_WEBSITE": "企业官网",
    "MANUAL_URL": "网页采集",
    "MANUAL_ENTRY": "人工录入",
    "GOV_TENDER": "招投标",
    "JOB_BOARD": "招聘平台",
    "NEWS": "新闻媒体",
}


def _source_distribution(db: Session, filters: RadarFilters) -> list[dict]:
    """机会来源占比：按机会证据关联的 Source.source_type 真实聚合（Donut 数据）。"""
    opp_ids = db.scalars(
        select(Opportunity.id)
        .join(Company, Opportunity.company_id == Company.id)
        .where(*filters.opp_filters())
    ).all()
    if not opp_ids:
        return []
    from app.models.source import Source, SourceRecord
    rows = db.execute(
        select(Source.source_type, func.count(func.distinct(OpportunityEvidence.opportunity_id)))
        .join(SourceRecord, OpportunityEvidence.source_record_id == SourceRecord.id)
        .join(Source, SourceRecord.source_id == Source.id)
        .where(OpportunityEvidence.opportunity_id.in_(opp_ids))
        .group_by(Source.source_type)
    ).all()
    # 有机会未挂任何来源记录时计为“未关联”
    total_opps = len(opp_ids)
    linked = sum(c for _, c in rows)
    result = [{"source_type": st, "label": SOURCE_CATEGORY.get(st, st), "count": c} for st, c in rows]
    if total_opps - linked > 0:
        result.append({"source_type": "UNLINKED", "label": "未关联来源", "count": total_opps - linked})
    return result


def _industry_options(db: Session) -> list[str]:
    """行业筛选下拉的真实选项（企业已标注的行业去重）。"""
    rows = db.execute(select(Company.industry).where(Company.industry.is_not(None)).distinct()).all()
    return sorted({r[0] for r in rows})


def build_radar_summary(db: Session, filters: RadarFilters) -> dict:
    """雷达总览（推荐结构）：空库返回真实 0 与空数组。"""
    return {
        "metrics": _metrics(db, filters),
        "locations": _locations(db, filters),
        "latest_signals": _latest_signals(db, filters),
        "top_opportunities": _top_opportunities(db, filters),
        "score_distribution": _score_distribution(db, filters),
        "source_distribution": _source_distribution(db, filters),
        "grade_distribution": _grade_distribution(db, filters),
        "pending_reviews": _pending_reviews(db),
        "industry_options": _industry_options(db),
    }
