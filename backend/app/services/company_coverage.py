"""T08.2 企业数据覆盖审计 / Coverage Gap / Enrichment Priority / Data Funnel（任务书四~六、三十二~三十四）。

全部代码聚合真实数据，不用 LLM 打分。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.source import SourceRecord
from app.services.actionability import compute_signal_actionability
from app.services.company_discovery import SECTION_PATTERNS
from app.services.company_quality import source_coverage
from app.services.validation_readiness import company_readiness

# 覆盖维度（任务书四）：URL/标题/正文三重判定
_COVER_DIMENSIONS: dict[str, str] = {
    "homepage_covered": "HOME",
    "news_covered": "NEWS",
    "careers_covered": "CAREERS",
    "products_covered": "PRODUCTS",
    "solutions_covered": "SOLUTIONS",
    "contact_covered": "CONTACT",
    "procurement_covered": "PROCUREMENT",
}


def _pattern_for(dimension: str):
    return SECTION_PATTERNS.get({
        "homepage_covered": "ABOUT", "news_covered": "NEWS", "careers_covered": "CAREERS",
        "products_covered": "PRODUCTS", "solutions_covered": "SOLUTIONS",
        "contact_covered": "CONTACT", "procurement_covered": None,
    }[dimension])


def coverage_audit_one(db: Session, company: Company) -> dict:
    """单家企业覆盖审计（任务书四字段全量输出）。"""
    records = db.scalars(select(SourceRecord).where(SourceRecord.company_id == company.id)).all()
    signals = db.scalars(select(Signal).where(Signal.company_id == company.id)).all()

    signal_status: dict[str, int] = {"actionable": 0, "historical": 0, "other": 0}
    for s in signals:
        if s.status != "APPROVED":
            continue
        a = compute_signal_actionability(db, s)
        if a == "ACTIONABLE_NOW":
            signal_status["actionable"] += 1
        elif a == "HISTORICAL_SIGNAL":
            signal_status["historical"] += 1
        else:
            signal_status["other"] += 1

    opp_count = db.scalar(select(func.count()).select_from(Opportunity).where(
        Opportunity.company_id == company.id)) or 0
    readiness = company_readiness(db, company.id)

    covered_dims = source_coverage(db, company.id).get("coverage", {})
    coverage: dict[str, bool] = {}
    for field, dimension in _COVER_DIMENSIONS.items():
        if field == "homepage_covered":
            coverage[field] = bool(company.website or company.domain)
        elif field == "procurement_covered":
            coverage[field] = bool(covered_dims.get("PROCUREMENT"))
        else:
            coverage[field] = bool(covered_dims.get(dimension)) or any(
                _pattern_for(field).search(f"{r.url or ''} {r.title or ''}") for r in records)
    contacts = db.scalars(select(CompanyContact).where(CompanyContact.company_id == company.id)).all()

    return {
        "company_id": company.id,
        "company_name": company.company_name,
        "organization_type": company.organization_type,
        "official_website": company.website,
        "domain": company.domain,
        "website_verified": company.verification_status == "WEBSITE_VERIFIED",
        "verification_status": company.verification_status,
        "industry": company.industry,
        "country": company.country or ("中国" if company.province else None),
        "province": company.province,
        "city": company.city,
        **coverage,
        "source_record_count": len(records),
        "contact_count": len(contacts),
        "approved_signal_count": sum(1 for s in signals if s.status == "APPROVED"),
        "actionable_signal_count": signal_status["actionable"],
        "historical_signal_count": signal_status["historical"],
        "opportunity_count": opp_count,
        "validation_ready": readiness["validation_ready"],
        "contact_ready": readiness["contact_ready"],
        "last_verified_at": company.verified_at.isoformat() if company.verified_at else None,
    }


def coverage_gap(audit: dict) -> list[str]:
    """覆盖缺口（任务书五）：缺失项列表，商业价值优先排序（Contact > Careers > News > Products > Solutions）。"""
    priority = ("contact_covered", "careers_covered", "news_covered", "products_covered",
                "solutions_covered", "homepage_covered")
    return [f for f in priority if not audit.get(f)]


def coverage_audit_all(db: Session, *, organization_type: str | None = "COMPANY") -> list[dict]:
    """全量覆盖审计（默认商业企业）。"""
    q = select(Company).where(Company.status == "ACTIVE")
    if organization_type:
        q = q.where(Company.organization_type == organization_type)
    results = []
    for c in db.scalars(q).all():
        audit = coverage_audit_one(db, c)
        audit["coverage_gap"] = coverage_gap(audit)
        results.append(audit)
    return results


# ---------------------------------------------------------------------------
# Enrichment Priority（任务书六：代码权重计算，不用 LLM）
# ---------------------------------------------------------------------------

WEIGHTS = {
    "opportunity_potential": 0.30,
    "recent_signal_presence": 0.20,
    "source_coverage_gap": 0.20,
    "commercial_company": 0.10,
    "website_verified": 0.10,
    "current_reachability": 0.10,
}


def enrichment_priority(db: Session, audit: dict) -> dict:
    """补全优先级（0~100）。分项均有真实数据依据：
    - opportunity_potential：已有 opportunity/actionable 信号越多潜力越高；
    - recent_signal_presence：近 30 天信号数；
    - source_coverage_gap：缺口越多越需要补全；
    - commercial_company / website_verified / current_reachability：现状分。
    """
    company = db.get(Company, audit["company_id"])
    now = datetime.now(timezone.utc)
    recent = 0
    for s in db.scalars(select(Signal).where(Signal.company_id == company.id, Signal.status.in_(["APPROVED", "VALID", "REVIEW"]))).all():
        anchor = s.collected_at
        if anchor and anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if anchor and (now - anchor) <= timedelta(days=30):
            recent += 1

    opportunity_potential = min(100, audit["opportunity_count"] * 40 + audit["actionable_signal_count"] * 30)
    recent_signal_presence = min(100, recent * 25)
    gap_count = len(audit["coverage_gap"])
    source_coverage_gap = min(100, gap_count * 25)
    commercial_company = 100 if audit["organization_type"] == "COMPANY" else 0
    website_verified = 100 if audit["website_verified"] else 40  # 有官网未验证也给部分分
    channels = company_readiness(db, company.id)["usable_contact_count"]
    current_reachability = min(100, channels * 50 + (40 if audit["official_website"] else 0))

    score = round(
        opportunity_potential * WEIGHTS["opportunity_potential"]
        + recent_signal_presence * WEIGHTS["recent_signal_presence"]
        + source_coverage_gap * WEIGHTS["source_coverage_gap"]
        + commercial_company * WEIGHTS["commercial_company"]
        + website_verified * WEIGHTS["website_verified"]
        + current_reachability * WEIGHTS["current_reachability"]
    )
    return {
        "company_id": company.id,
        "company_name": company.company_name,
        "priority_score": score,
        "factors": {
            "opportunity_potential": opportunity_potential,
            "recent_signal_presence": recent_signal_presence,
            "source_coverage_gap": source_coverage_gap,
            "commercial_company": commercial_company,
            "website_verified": website_verified,
            "current_reachability": current_reachability,
        },
        "coverage_gap": audit["coverage_gap"],
        "official_website": audit["official_website"],
    }


def top_enrichment_targets(db: Session, *, organization_type: str = "COMPANY", limit: int = 20) -> list[dict]:
    """Top N 补全目标（任务书七）。"""
    audits = coverage_audit_all(db, organization_type=organization_type)
    ranked = [enrichment_priority(db, a) for a in audits]
    ranked.sort(key=lambda x: -x["priority_score"])
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Data Funnel（任务书三十三）与场景分布（任务书三十/三十二）
# ---------------------------------------------------------------------------

_SCENARIO_MAP: dict[str, str] = {
    "SALES_HIRING": "CUSTOMER_ACQUISITION",
    "OVERSEAS_EXPANSION": "OVERSEAS_EXPANSION",
    "AI_HIRING": "AI_TRANSFORMATION",
    "AI_DEMAND": "AI_TRANSFORMATION",
    "AI_TRANSFORMATION": "AI_TRANSFORMATION",
    "CUSTOMER_SERVICE_HIRING": "CUSTOMER_SERVICE",
    "HIRING": "RECRUITMENT",
    "TECH_HIRING": "RECRUITMENT",
    "FINANCE_HIRING": "RECRUITMENT",
    "PROCUREMENT_HIRING": "RECRUITMENT",
    "SUPPLY_CHAIN_HIRING": "RECRUITMENT",
    "PROCUREMENT": "PROCUREMENT",
    "TENDER": "PROCUREMENT",
    "SUPPLIER_SEARCH": "PROCUREMENT",
    "CRM_DEMAND": "SALES_EFFICIENCY",
    "AUTOMATION_DEMAND": "PROCESS_AUTOMATION",
    "DIGITAL_TRANSFORMATION": "DIGITAL_TRANSFORMATION",
    "NEW_PRODUCT": "NEW_PRODUCT",
    "NEW_SERVICE": "NEW_PRODUCT",
    "NEW_MARKET": "NEW_MARKET",
    "NEW_FACTORY": "EXPANSION",
    "NEW_OFFICE": "EXPANSION",
    "EXPANSION": "EXPANSION",
    "FUNDING": "FUNDING",
    "PARTNERSHIP": "PARTNERSHIP",
    "STRATEGIC_COOPERATION": "PARTNERSHIP",
}


def scenario_distribution(db: Session) -> dict[str, int]:
    """商业场景分布（仅 Approved + 可行动信号；历史采购不计入）。"""
    signals = db.scalars(select(Signal).where(Signal.status == "APPROVED")).all()
    distribution: dict[str, int] = {}
    for s in signals:
        a = compute_signal_actionability(db, s)
        if a not in {"ACTIONABLE_NOW", "WATCH"}:
            continue
        scenario = _SCENARIO_MAP.get(s.signal_type)
        if scenario:
            distribution[scenario] = distribution.get(scenario, 0) + 1
    return dict(sorted(distribution.items(), key=lambda kv: -kv[1]))


def data_funnel(db: Session) -> dict:
    """数据漏斗（全部真实聚合）。"""
    companies = db.scalars(select(Company).where(Company.status == "ACTIVE")).all()
    commercial = [c for c in companies if c.organization_type == "COMPANY"]
    funnel_companies = commercial  # 漏斗按商业企业统计

    with_signal: list[Company] = []
    with_actionable: list[Company] = []
    with_opportunity: list[Company] = []
    validation_ready: list[Company] = []
    contact_ready: list[Company] = []
    covered: list[Company] = []
    for c in funnel_companies:
        signals = db.scalars(select(Signal).where(Signal.company_id == c.id)).all()
        if signals:
            with_signal.append(c)
        if any(s.status == "APPROVED" and compute_signal_actionability(db, s) == "ACTIONABLE_NOW" for s in signals):
            with_actionable.append(c)
        if db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.company_id == c.id)):
            with_opportunity.append(c)
        readiness = company_readiness(db, c.id)
        if readiness["validation_ready"]:
            validation_ready.append(c)
        if readiness["contact_ready"]:
            contact_ready.append(c)
        cov = source_coverage(db, c.id).get("coverage", {})
        if sum(1 for v in cov.values() if v) >= 3:
            covered.append(c)

    total = len(funnel_companies)

    def rate(n: int) -> float:
        return round(n / total, 4) if total else 0.0

    return {
        "commercial_companies": total,
        "covered_companies": len(covered),
        "companies_with_signals": len(with_signal),
        "companies_with_actionable_signals": len(with_actionable),
        "companies_with_opportunities": len(with_opportunity),
        "validation_ready": len(validation_ready),
        "contact_ready": len(contact_ready),
        "rates": {
            "signal_coverage_rate": rate(len(with_signal)),
            "actionable_signal_rate": rate(len(with_actionable)),
            "opportunity_rate": rate(len(with_opportunity)),
            "validation_ready_rate": rate(len(validation_ready)),
            "contact_ready_rate": rate(len(contact_ready)),
        },
    }
