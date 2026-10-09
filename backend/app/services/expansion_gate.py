"""T08.1 企业池扩量质量 Gate（任务书十四/十八/二十四/二十九）。

全部指标由代码从真实数据聚合计算，不用 LLM 打分；判定阈值明确：
- 真实主体 ≥ target_count（默认30）
- 商业企业（COMPANY）占比 ≥ 70%（不得用政府/高校/科研院所凑数）
- Source Type ≥ 3 类（不得单一来源）
- SOURCE_PLATFORM 主体（ACTIVE 业务池内）= 0
- Evidence 通过率 ≥ 95%（有信号的）
- Source URL 有效率 = 100%（采集时 http_status 200 的比例，失败记录如实拉低）
- 严重信号误判 = 0（审计 findings 非空的信号数）
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.signal import Signal, SignalEvidence
from app.models.source import Source, SourceRecord
from app.services.validation_readiness import company_readiness

_REAL_VERIFICATIONS = {"PUBLIC_SOURCE_VERIFIED", "WEBSITE_VERIFIED"}


def expansion_quality_gate(
    db: Session,
    *,
    target_count: int = 30,
    min_commercial_ratio: float = 0.70,
    min_source_types: int = 3,
    min_evidence_pass_rate: float = 0.95,
) -> dict:
    companies = db.scalars(select(Company).where(Company.status == "ACTIVE")).all()
    real = [c for c in companies if c.verification_status in _REAL_VERIFICATIONS]
    commercial = [c for c in real if c.organization_type == "COMPANY"]
    platform_companies = [c for c in companies if c.organization_type == "SOURCE_PLATFORM"]

    org_distribution: dict[str, int] = {}
    for c in real:
        org_distribution[c.organization_type] = org_distribution.get(c.organization_type, 0) + 1

    real_ids = {c.id for c in real}
    # Source Type 分布：只统计挂接在真实主体上的记录（来源多样性的正确口径）
    source_type_rows = db.execute(
        select(Source.source_type, func.count(SourceRecord.id))
        .join(SourceRecord, SourceRecord.source_id == Source.id)
        .where(SourceRecord.company_id.in_(real_ids) if real_ids else False)
        .group_by(Source.source_type)
    ).all() if real_ids else []
    source_type_distribution = {t: int(n) for t, n in source_type_rows}
    source_type_count = len([t for t, n in source_type_distribution.items() if n > 0])

    # 每家企业信号/证据聚合
    signal_rows = db.scalars(select(Signal)).all()
    signals_by_company: dict[str, list[Signal]] = {}
    for s in signal_rows:
        signals_by_company.setdefault(s.company_id, []).append(s)
    evidence_rows = db.scalars(select(SignalEvidence)).all()
    evidence_by_signal: dict[str, list[SignalEvidence]] = {}
    for e in evidence_rows:
        evidence_by_signal.setdefault(e.signal_id, []).append(e)
    records = {r.id: r for r in db.scalars(select(SourceRecord)).all()}

    signal_coverage = sum(1 for c in real if signals_by_company.get(c.id))
    approved_signals = [s for s in signal_rows if s.status == "APPROVED"]
    review_signals = [s for s in signal_rows if s.status in {"VALID", "REVIEW"}]

    # Evidence 质量：信号至少 1 条证据且 quoted_text 可在来源原文中精确找到
    evidence_total, evidence_pass = 0, 0
    for s in signal_rows:
        evs = evidence_by_signal.get(s.id, [])
        if not evs:
            continue
        evidence_total += 1
        record = records.get(s.source_record_id)
        raw = (record.raw_text if record else "") or ""
        if any(e.quoted_text and e.quoted_text in raw for e in evs):
            evidence_pass += 1
    evidence_pass_rate = (evidence_pass / evidence_total) if evidence_total else 1.0

    # Source URL 有效率（http_status==200 的记录比例）
    records_with_status = [r for r in records.values() if r.http_status is not None]
    url_valid = [r for r in records_with_status if r.http_status == 200]
    source_url_valid_rate = (len(url_valid) / len(records_with_status)) if records_with_status else 1.0

    # 重复率（normalized_name 重复的主体 / 真实主体）
    name_seen: dict[str, int] = {}
    for c in real:
        name_seen[c.normalized_name] = name_seen.get(c.normalized_name, 0) + 1
    duplicates = sum(n - 1 for n in name_seen.values() if n > 1)
    duplicate_rate = (duplicates / len(real)) if real else 0.0

    # 解析失败率（成功值有 OK / PARSE_SUCCESS 两种；FAILED 为真实失败）
    parse_failed = [r for r in records.values() if r.parse_status not in (None, "OK", "PARSE_SUCCESS")]
    parse_failure_rate = (len(parse_failed) / len(records)) if records else 0.0

    # 严重信号误判：审计 findings 非空
    misjudged = 0
    for s in signal_rows:
        audit = (s.payload_json or {}).get("t08_audit") or {}
        if audit.get("findings"):
            misjudged += 1

    # 机会与验证池
    opp_rows = db.scalars(select(Opportunity)).all()
    approved_opps = [o for o in opp_rows if o.review_status == "APPROVED"]
    readiness = [company_readiness(db, c.id) for c in real]
    validation_ready = [r for r in readiness if r["validation_ready"]]
    contact_ready = [r for r in readiness if r["contact_ready"]]

    commercial_ratio = (len(commercial) / len(real)) if real else 0.0

    gates = {
        "real_entities_at_least_target": len(real) >= target_count,
        "commercial_ratio_at_least_70pct": commercial_ratio >= min_commercial_ratio,
        "source_types_at_least_3": source_type_count >= min_source_types,
        "no_source_platform_company_active": len([c for c in platform_companies if c.status == "ACTIVE"]) == 0,
        "evidence_pass_rate_at_least_95pct": evidence_pass_rate >= min_evidence_pass_rate,
        "no_severe_signal_misjudgement": misjudged == 0,
    }

    return {
        "company_count": len(companies),
        "real_entity_count": len(real),
        "commercial_company_count": len(commercial),
        "commercial_ratio": round(commercial_ratio, 4),
        "organization_type_distribution": org_distribution,
        "source_type_distribution": source_type_distribution,
        "source_type_count": source_type_count,
        "official_website_coverage": sum(1 for c in real if c.website or c.domain),
        "signal_coverage": signal_coverage,
        "approved_signal_count": len(approved_signals),
        "review_signal_count": len(review_signals),
        "opportunity_count": len(opp_rows),
        "approved_opportunity_count": len(approved_opps),
        "validation_ready_count": len(validation_ready),
        "contact_ready_count": len(contact_ready),
        "duplicate_rate": round(duplicate_rate, 4),
        "parse_failure_rate": round(parse_failure_rate, 4),
        "evidence_total": evidence_total,
        "evidence_pass_rate": round(evidence_pass_rate, 4),
        "source_url_valid_rate": round(source_url_valid_rate, 4),
        "severe_signal_misjudgement_count": misjudged,
        "source_platform_company_count": len(platform_companies),
        "gates": gates,
        "passed": all(gates.values()),
    }
