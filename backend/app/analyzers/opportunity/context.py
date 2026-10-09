"""分析上下文组装：把企业的真实数据（已批准 Signal、原文证据、来源等级、联系人、时间密度）
汇总为一次机会分析的输入。只读取真实字段，Unknown 字段不补充。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.signal import Signal, SignalEvidence
from app.models.source import Source, SourceRecord


@dataclass
class SignalContext:
    signal: Signal
    evidences: list[SignalEvidence] = field(default_factory=list)
    source_grade: str = "C"
    record: SourceRecord | None = None

    @property
    def supporting_evidences(self) -> list[SignalEvidence]:
        return list(self.evidences)

    @property
    def newest_evidence_at(self) -> datetime | None:
        times = [e.created_at for e in self.evidences if e.created_at]
        times.append(self.signal.last_seen_at or self.signal.collected_at)
        times = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times if t]
        return max(times) if times else None


@dataclass
class CompanyAnalysisContext:
    company: Company
    signals: list[SignalContext] = field(default_factory=list)
    contacts: list[CompanyContact] = field(default_factory=list)
    signal_count_7d: int = 0
    signal_count_30d: int = 0
    signal_count_90d: int = 0

    @property
    def signal_types(self) -> set[str]:
        return {s.signal.signal_type for s in self.signals}

    @property
    def evidence_count(self) -> int:
        return sum(len(s.evidences) for s in self.signals)

    @property
    def best_source_grade(self) -> str:
        order = ["A", "B", "C", "D"]
        grades = [s.source_grade for s in self.signals]
        for g in order:
            if g in grades:
                return g
        return "D"

    @property
    def newest_signal_at(self) -> datetime | None:
        times = [s.signal.last_seen_at or s.signal.collected_at for s in self.signals]
        times = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times if t]
        return max(times) if times else None


def load_company_context(db: Session, company_id: str, *, now: datetime | None = None) -> CompanyAnalysisContext | None:
    """加载企业的真实分析上下文。无已批准 Signal 时返回 signals 为空列表。"""
    company = db.get(Company, company_id)
    if not company:
        return None
    now = now or datetime.now(timezone.utc)
    ctx = CompanyAnalysisContext(company=company)

    signals = db.scalars(
        select(Signal).where(Signal.company_id == company_id, Signal.status == "APPROVED").order_by(Signal.collected_at.desc())
    ).all()
    records: dict[str, SourceRecord] = {}
    sources: dict[str, Source] = {}
    for signal in signals:
        from app.services.evidence_integrity import signal_issues
        if signal_issues(db, signal):
            continue
        sc = SignalContext(signal=signal)
        sc.evidences = list(db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == signal.id)).all())
        record = records.get(signal.source_record_id)
        if record is None:
            record = db.get(SourceRecord, signal.source_record_id)
            records[signal.source_record_id] = record
        sc.record = record
        if record is not None:
            source = sources.get(record.source_id)
            if source is None:
                source = db.get(Source, record.source_id)
                sources[record.source_id] = source
            from app.services.reliability import effective_grade
            sc.source_grade = effective_grade(record.source_reliability or (source.reliability_grade if source else 'C'))
        ctx.signals.append(sc)

    ctx.contacts = list(db.scalars(select(CompanyContact).where(CompanyContact.company_id == company_id)).all())

    # 时间密度：真实 Signal 历史（含全部状态历史？仅 APPROVED/REVIEW 有效信号），按任务书取真实计数
    valid = db.scalars(select(Signal).where(Signal.company_id == company_id, Signal.status.in_(["APPROVED", "REVIEW"]))).all()
    for signal in valid:
        anchor = signal.last_seen_at or signal.collected_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        age_days = (now - anchor).days
        if age_days <= 7:
            ctx.signal_count_7d += 1
        if age_days <= 30:
            ctx.signal_count_30d += 1
        if age_days <= 90:
            ctx.signal_count_90d += 1
    return ctx
