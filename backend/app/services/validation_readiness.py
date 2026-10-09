"""T08.2 Validation Ready / Contact Ready 判定 v2（任务书二十八/二十九）。

Validation Ready（机会就绪）：
  - 真实 Company（verification_status != UNVERIFIED）
  - organization_type = COMPANY 优先（列表可按此过滤，不作为硬门槛）
  - Approved Opportunity >= 1（已人工审核）
  - Approved Signal >= 1
  - T08.2：存在 ACTIONABLE_NOW 的 Approved Signal >= 1（WATCH 不再满足本门；
    HISTORICAL_SIGNAL/NOT_ACTIONABLE 的历史采购不得进入）
  - Evidence Count >= 1 且 Opportunity Evidence Score >= 60
  - Source URL 有效
Contact Ready（联系就绪，任务书二十九新定义）：
  - validation_ready = true 且至少 1 个 VERIFIED_PUBLIC Contact 或官方 WEBSITE_FORM
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.services.actionability import (
    is_actionable_for_validation,
    opportunity_actionability,
    compute_signal_actionability,
)


def usable_contact_channels(db: Session, company_id: str) -> list[dict]:
    """企业可用联系渠道（VERIFIED_PUBLIC / USER_PROVIDED；含 WEBSITE_FORM）。"""
    contacts = db.scalars(select(CompanyContact).where(
        CompanyContact.company_id == company_id,
        CompanyContact.verification_status.in_(["VERIFIED_PUBLIC", "USER_PROVIDED"]),
    )).all()
    channels = []
    for c in contacts:
        channel = "EMAIL" if c.email else ("PHONE" if c.phone else ("WEBSITE_FORM" if c.public_profile_url else None))
        if channel:
            channels.append({
                "contact_id": c.id, "channel": channel, "contact_type": c.contact_type,
                "email": c.email, "phone": c.phone, "form_url": c.public_profile_url,
            })
    return channels


def company_readiness(db: Session, company_id: str) -> dict:
    """单家企业的就绪状态（validation_ready / contact_ready 分开）。"""
    company = db.get(Company, company_id)
    if company is None:
        return {"company_id": company_id, "validation_ready": False, "contact_ready": False, "checks": {}}

    approved_opps = db.scalars(select(Opportunity).where(
        Opportunity.company_id == company_id,
        Opportunity.review_status == "APPROVED",
        Opportunity.status == "ACTIVE",
    )).all()
    approved_signals = db.scalars(select(Signal).where(
        Signal.company_id == company_id, Signal.status == "APPROVED",
    )).all()
    from app.services.evidence_integrity import signal_issues, opportunity_issues
    approved_signals = [s for s in approved_signals if not signal_issues(db, s)]
    approved_opps = [o for o in approved_opps if not opportunity_issues(db, o)]
    evidence_count = sum(len(o.evidences) for o in approved_opps)
    best_evidence_score = max((o.evidence_score for o in approved_opps), default=0)

    # T08.2：Actionability Analyzer 判定（审计结果 > 显式块 > 规则）
    signal_actionability_map = {s.id: compute_signal_actionability(db, s) for s in approved_signals}
    actionable_now_count = sum(1 for v in signal_actionability_map.values() if v == "ACTIONABLE_NOW")

    channels = usable_contact_channels(db, company_id)

    # T08.1：机会可行动性（历史采购/已中标的机会不进入 ACTIONABLE 验证池）
    opportunity_actionability_map = {
        opp.id: opportunity_actionability(db, opp)["actionability_status"] for opp in approved_opps
    }
    actionable_opp_count = sum(
        1 for status in opportunity_actionability_map.values() if is_actionable_for_validation(status)
    )

    checks = {
        "company_verified": company.verification_status != "UNVERIFIED",
        "approved_opportunity": len(approved_opps) >= 1,
        "approved_signal": len(approved_signals) >= 1,
        "actionable_now_signal": actionable_now_count >= 1,
        "evidence_count": evidence_count >= 1,
        "evidence_score": best_evidence_score >= 60,
        "source_url_effective": bool(company.discovery_source_url or company.website or company.domain),
        "actionable_opportunity": actionable_opp_count >= 1,
    }
    validation_ready = all(checks.values())
    # T08.2 二十九：contact_ready = validation_ready 且有可用联系渠道
    contact_ready = validation_ready and len(channels) >= 1
    return {
        "company_id": company_id,
        "company_name": company.company_name,
        "organization_type": company.organization_type,
        "validation_ready": validation_ready,
        "contact_ready": contact_ready,
        "checks": checks,
        "approved_opportunity_count": len(approved_opps),
        "approved_signal_count": len(approved_signals),
        "actionable_now_signal_count": actionable_now_count,
        "evidence_count": evidence_count,
        "best_evidence_score": best_evidence_score,
        "usable_contact_count": len(channels),
        "usable_contact_channels": channels,
        "opportunity_actionability": opportunity_actionability_map,
        "signal_actionability": signal_actionability_map,
        "actionable_opportunity_count": actionable_opp_count,
        "failed_checks": [k for k, v in checks.items() if not v],
    }


def list_validation_ready(db: Session, *, organization_type: str | None = "COMPANY", contact_ready_only: bool = False) -> dict:
    """Validation Ready 企业列表（默认仅商业企业；可含全部类型）。"""
    companies = db.scalars(select(Company).where(Company.status == "ACTIVE")).all()
    items = []
    for company in companies:
        if organization_type and company.organization_type != organization_type:
            continue
        state = company_readiness(db, company.id)
        if not state["validation_ready"]:
            continue
        if contact_ready_only and not state["contact_ready"]:
            continue
        items.append(state)
    items.sort(key=lambda x: (-x["best_evidence_score"], -x["approved_signal_count"]))
    return {
        "validation_ready_count": len(items),
        "contact_ready_count": sum(1 for x in items if x["contact_ready"]),
        "items": items,
    }
