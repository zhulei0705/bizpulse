"""T07 市场验证候选排序（Market Validation Ranking）。

原则（任务书四/五/七）：
- 从真实数据库聚合，不拍脑袋定行业；细分到"什么企业 + 什么问题"场景（以机会的
  pain_category 为场景轴），不是大行业；
- 系统只做排序/总结/解释，**哪个市场进入第一轮验证由人工决定**；
- 每个候选的统计全部来自 APPROVED 信号与已审核机会，没有真实数据时为 0。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import PAIN_CATEGORIES
from app.models.company import Company, CompanyContact
from app.models.experiment import Interaction
from app.models.opportunity import Opportunity
from app.models.pain_point import PainPoint
from app.models.signal import Signal


def market_validation_candidates(db: Session, *, min_companies: int = 1) -> list[dict]:
    """按细分场景聚合真实数据，输出市场验证候选（已按推荐度排序）。

    场景轴 = 已审核机会的 pain_category；统计口径：
    - company_count: 该场景下有已审核机会的真实企业数
    - signal_count / fresh_signal_count_30d: 这些企业的 APPROVED 信号（全部 / 30 天内）
    - avg_*: 已审核机会的平均分（预测能力指标）
    - reachable_company_count: 有真实可用联系人（VERIFIED_PUBLIC/USER_PROVIDED）的企业数
    - replied_company_count: 该场景真实有过客户回复（REPLY 互动）的企业数
    """
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)

    opportunities = db.scalars(
        select(Opportunity).where(Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE")
    ).all()
    from app.services.evidence_integrity import opportunity_issues,signal_issues
    opportunities=[o for o in opportunities if not opportunity_issues(db,o)]
    if not opportunities:
        return []

    company_ids = {o.company_id for o in opportunities if o.company_id}
    companies = {c.id: c for c in db.scalars(select(Company).where(Company.id.in_(company_ids))).all()} if company_ids else {}

    # 场景轴：机会关联 PainPoint 的 category（Opportunity 本身没有 pain_category）
    pain_point_ids = {o.pain_point_id for o in opportunities if o.pain_point_id}
    pain_categories = {
        p.id: p.category
        for p in db.scalars(select(PainPoint).where(PainPoint.id.in_(pain_point_ids))).all()
    } if pain_point_ids else {}

    # 企业级 APPROVED 信号
    signals = db.scalars(
        select(Signal).where(Signal.status == "APPROVED", Signal.company_id.in_(company_ids))
    ).all() if company_ids else []
    signals=[s for s in signals if not signal_issues(db,s)]
    signals_by_company: dict[str, list[Signal]] = {}
    for s in signals:
        signals_by_company.setdefault(s.company_id, []).append(s)

    # 可触达：有真实可用联系人的企业
    contacts = db.scalars(
        select(CompanyContact).where(
            CompanyContact.company_id.in_(company_ids),
            CompanyContact.verification_status.in_(["VERIFIED_PUBLIC", "USER_PROVIDED"]),
        )
    ).all() if company_ids else []
    reachable_company_ids = {c.company_id for c in contacts}

    # 真实有过回复的企业（REPLY 互动，按互动的企业去重）
    reply_rows = db.scalars(
        select(Interaction.company_id).where(Interaction.interaction_type == "REPLY", Interaction.company_id.in_(company_ids))
    ).all() if company_ids else []
    replied_company_ids = set(reply_rows)

    # 按场景聚合
    groups: dict[str, list[Opportunity]] = {}
    for o in opportunities:
        category = pain_categories.get(o.pain_point_id) if o.pain_point_id else None
        groups.setdefault(category or "OTHER", []).append(o)

    candidates: list[dict] = []
    for category, opps in groups.items():
        cat_company_ids = {o.company_id for o in opps if o.company_id}
        cat_signals = [s for cid in cat_company_ids for s in signals_by_company.get(cid, [])]
        avg_opp = sum(o.total_score for o in opps) / len(opps)
        avg_evidence = sum(o.evidence_score for o in opps) / len(opps)
        avg_intent = sum(o.intent_score for o in opps) / len(opps)
        high_value = sum(1 for o in opps if o.total_score >= 75 or o.grade in {"S", "A", "B"})

        def _aware(dt: datetime) -> datetime:
            return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt

        fresh = sum(1 for s in cat_signals if s.collected_at and _aware(s.collected_at) >= cutoff_30d)
        industries = sorted({(companies[cid].industry or "未知") for cid in cat_company_ids if cid in companies})
        candidates.append({
            "market_name": f"{PAIN_CATEGORIES.get(category, category)}场景",
            "target_customer": "、".join(industries) or "—",
            "primary_pain": category,
            "primary_pain_label": PAIN_CATEGORIES.get(category, category),
            "company_count": len(cat_company_ids),
            "signal_count": len(cat_signals),
            "opportunity_count": len(opps),
            "avg_opportunity_score": round(avg_opp, 1),
            "avg_evidence_score": round(avg_evidence, 1),
            "avg_intent_score": round(avg_intent, 1),
            "high_value_opportunity_count": high_value,
            "reachable_company_count": len(cat_company_ids & reachable_company_ids),
            "replied_company_count": len(cat_company_ids & replied_company_ids),
            "fresh_signal_count_30d": fresh,
            "company_names": sorted({companies[cid].company_name for cid in cat_company_ids if cid in companies}),
        })

    # 过滤数据过少的场景
    candidates = [c for c in candidates if c["company_count"] >= min_companies]

    # 推荐排序（透明规则）：机会数量 > 平均机会分 > 30 天新鲜信号 > 可触达企业
    candidates.sort(key=lambda c: (
        c["opportunity_count"],
        c["avg_opportunity_score"],
        c["fresh_signal_count_30d"],
        c["reachable_company_count"],
    ), reverse=True)
    for rank, c in enumerate(candidates, start=1):
        c["rank"] = rank
        c["recommendation_basis"] = (
            f"机会 {c['opportunity_count']} 个（均分 {c['avg_opportunity_score']}）、"
            f"APPROVED 信号 {c['signal_count']} 条（30 天内 {c['fresh_signal_count_30d']} 条）、"
            f"可触达企业 {c['reachable_company_count']}/{c['company_count']}"
        )
    return candidates


def data_sufficiency(db: Session, *, target_count: int = 30) -> dict:
    """第一轮 30 家验证的数据充足性评估（任务书六十三/六十四：不足就如实报缺口，不硬凑）。"""
    approved_opps = db.scalars(
        select(Opportunity).where(Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE")
    ).all()
    from app.services.evidence_integrity import opportunity_issues
    approved_opps=[o for o in approved_opps if not opportunity_issues(db,o)]
    company_ids = {o.company_id for o in approved_opps if o.company_id}
    approved_signal_count = db.scalar(
        select(Signal.id).where(Signal.status == "APPROVED").order_by(Signal.id).limit(1)
    )
    from sqlalchemy import func
    approved_signal_total = db.scalar(select(func.count()).select_from(Signal).where(Signal.status == "APPROVED")) or 0
    company_total = db.scalar(select(func.count()).select_from(Company)) or 0
    eligible = len(company_ids)

    shortfall = max(0, target_count - eligible)
    return {
        "company_count": company_total,
        "approved_signal_count": approved_signal_total if approved_signal_total or approved_signal_count else 0,
        "opportunity_count": len(approved_opps),
        "eligible_company_count": eligible,
        "target_count": target_count,
        "shortfall": shortfall,
        "sufficient": shortfall == 0,
        "message": (
            "数据充足，可以建立第一轮验证 Experiment"
            if shortfall == 0
            else f"真实数据不足：满足筛选条件的企业 {eligible} 家，第一轮目标 {target_count} 家，缺口 {shortfall} 家。建议先继续真实数据采集，不要硬凑。"
        ),
    }
