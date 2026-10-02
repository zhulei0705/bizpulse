"""T05 测试辅助：构建分析上下文与持久化测试数据。"""
from datetime import datetime, timedelta, timezone

from app.models.company import Company
from app.models.opportunity_candidate import OpportunityCandidate, SignalBundle
from app.models.signal import Signal, SignalEvidence
from app.models.source import Source, SourceRecord


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_signal(
    signal_id: str,
    signal_type: str,
    *,
    company_id: str = "cmp_test",
    confidence: int = 80,
    grade: str = "A",
    fact: str | None = None,
    title: str | None = None,
    age_days: int = 1,
    change_type: str | None = None,
    change_value: str | None = None,
    evidence_text: str | None = None,
    fingerprint: str | None = None,
) -> "SignalContext-like":
    """构建内存 SignalContext（不落库，纯分析器单元测试用）。"""
    from app.analyzers.opportunity.context import SignalContext

    now = utcnow()
    signal = Signal(
        id=signal_id,
        company_id=company_id,
        source_record_id=f"rec_{signal_id}",
        signal_type=signal_type,
        title=title or f"{signal_type} 信号",
        confidence=confidence,
        reliability_score={"A": 90, "B": 80, "C": 60, "D": 40}.get(grade, 50),
        status="APPROVED",
        fact_or_inference="FACT",
        fact_summary=fact or f"{signal_type} 事实摘要",
        collected_at=now - timedelta(days=age_days),
        published_at=now - timedelta(days=age_days),
        change_type=change_type,
        change_value=change_value,
        signal_fingerprint=fingerprint or f"fp_{signal_id}",
        created_at=now - timedelta(days=age_days),
    )
    ctx = SignalContext(signal=signal)
    if evidence_text:
        ctx.evidences = [SignalEvidence(
            signal_id=signal_id,
            source_record_id=f"rec_{signal_id}",
            quoted_text=evidence_text,
            confidence=confidence,
            created_at=now - timedelta(days=age_days),
        )]
    ctx.source_grade = grade
    return ctx


def make_company_context(signals: list, **company_fields) -> "CompanyAnalysisContext":
    from app.analyzers.opportunity.context import CompanyAnalysisContext

    defaults = dict(
        id="cmp_test",
        company_name="测试企业",
        normalized_name="测试企业",
        website="https://www.test-company.com",
        domain="test-company.com",
        employee_range="50-100",
    )
    defaults.update(company_fields)
    company = Company(**defaults)
    company.id = defaults["id"]
    ctx = CompanyAnalysisContext(company=company, signals=signals)
    for sc in signals:
        if sc.newest_evidence_at and (utcnow() - sc.newest_evidence_at).days <= 7:
            ctx.signal_count_7d += 1
        if sc.newest_evidence_at and (utcnow() - sc.newest_evidence_at).days <= 30:
            ctx.signal_count_30d += 1
        if sc.newest_evidence_at and (utcnow() - sc.newest_evidence_at).days <= 90:
            ctx.signal_count_90d += 1
    return ctx


def persist_signal(
    db,
    company: Company,
    source: Source,
    record: SourceRecord,
    signal_type: str,
    *,
    confidence: int = 80,
    fact_summary: str | None = None,
    evidence_text: str | None = None,
    fingerprint: str | None = None,
    age_days: int = 1,
) -> Signal:
    now = utcnow()
    signal = Signal(
        company_id=company.id,
        source_record_id=record.id,
        signal_type=signal_type,
        title=f"{signal_type}：{record.title or record.url}"[:500],
        confidence=confidence,
        reliability_score=source.reliability_score if source is not None else 50,
        status="APPROVED",
        fact_or_inference="FACT",
        fact_summary=fact_summary or f"原文事实：{signal_type}",
        collected_at=now - timedelta(days=age_days),
        published_at=now - timedelta(days=age_days),
        first_seen_at=now - timedelta(days=age_days),
        last_seen_at=now - timedelta(days=age_days),
        signal_fingerprint=fingerprint,
        created_by="RULE",
        payload_json={},
    )
    db.add(signal)
    db.flush()
    if evidence_text:
        db.add(SignalEvidence(
            signal_id=signal.id,
            source_record_id=record.id,
            quoted_text=evidence_text,
            confidence=confidence,
        ))
    db.flush()
    return signal


def persist_company_with_source(db, *, name: str = "测试企业", grade: str = "A", domain: str = "test-company.com"):
    company = Company(company_name=name, normalized_name=name.lower(), domain=domain, website=f"https://www.{domain}")
    db.add(company)
    db.flush()
    source = Source(name=f"{name}来源", source_type="OFFICIAL_WEBSITE", reliability_grade=grade,
                    reliability_score={"A": 90, "B": 80, "C": 60, "D": 40}.get(grade, 50))
    db.add(source)
    db.flush()
    record = SourceRecord(
        source_id=source.id, company_id=company.id, url=f"https://www.{domain}/news",
        content_hash=f"hash-{name}-{utcnow().timestamp()}", raw_text="测试正文",
    )
    db.add(record)
    db.flush()
    return company, source, record
