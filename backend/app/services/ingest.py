"""手动 URL 分析编排：

URL 校验 → 抓取 → Source/SourceRecord → 企业识别 → Company 创建/匹配
→ 规则提取 Signal（+ 可选 LLM 增强）→ 可选 PainPoint/Opportunity（仅 LLM 配置时）

原则：
- NO_FAKE_DATA：不产生任何虚构数据；
- LLM 未配置时不阻塞：保存 SourceRecord + Company + 规则信号，允许人工补建；
- 内容指纹去重：同一 URL 同一内容不重复采集。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm import get_llm_adapter
from app.models.company import Company
from app.models.pain_point import PainPoint, PainPointEvidence
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.services import extractor
from app.services.audit import write_audit

logger = logging.getLogger(__name__)

MANUAL_SOURCE_NAME = "手动URL分析"
MANUAL_SOURCE_TYPE = "MANUAL_URL"


@dataclass
class IngestResult:
    source_id: str
    source_record_id: str
    company_id: str | None
    signal_ids: list[str] = field(default_factory=list)
    pain_point_ids: list[str] = field(default_factory=list)
    opportunity_ids: list[str] = field(default_factory=list)
    llm_configured: bool = False
    duplicate: bool = False
    message: str | None = None


def _normalize_name(name: str) -> str:
    return "".join(name.lower().split())


def get_manual_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.source_type == MANUAL_SOURCE_TYPE))
    if source:
        return source
    source = Source(
        name=MANUAL_SOURCE_NAME,
        source_type=MANUAL_SOURCE_TYPE,
        base_url=None,
        reliability_grade="C",
        reliability_score=55,
        enabled=True,
        collector_type="manual_url",
        notes="用户手动输入的公开网页 URL。默认 C 级可信度，可在数据源页面调整。",
    )
    db.add(source)
    db.flush()
    return source


def resolve_or_create_company(db: Session, name: str | None, page: extractor.FetchedPage) -> Company | None:
    """按 域名 → normalized_name 匹配；匹配不到时用可识别名称创建。识别不了返回 None。"""
    host = extractor.domain_of(page.final_url)
    company: Company | None = None
    if host:
        company = db.scalar(select(Company).where(Company.domain == host))
    if company is None and name:
        company = db.scalar(select(Company).where(Company.normalized_name == _normalize_name(name)))
    if company:
        if not company.website and extractor.site_origin(page.final_url):
            company.website = extractor.site_origin(page.final_url)
        return company
    if not name:
        return None
    company = Company(
        company_name=name[:300],
        normalized_name=_normalize_name(name)[:300] or name.lower()[:300],
        domain=host,
        website=extractor.site_origin(page.final_url),
        company_description=(page.meta_description or None),
        source_count=0,
    )
    db.add(company)
    db.flush()
    write_audit(db, "CREATE", "company", company.id, {"company_name": company.company_name, "via": "ingest_url"})
    return company


def _source_score(db: Session, source_id: str) -> int:
    source = db.get(Source, source_id)
    return int(source.reliability_score) if source else 50


def create_rule_signals(db: Session, company: Company | None, record: SourceRecord, page: extractor.FetchedPage) -> list[Signal]:
    """规则引擎信号提取：仅基于真实正文，逐条关联 source_record（T02 行为，T03 复用）。"""
    hits = extractor.extract_signal_hits(page)
    signals: list[Signal] = []
    for hit in hits:
        signal = Signal(
            company_id=company.id if company else None,
            source_record_id=record.id,
            signal_type=hit.signal_type,
            title=f"{hit.title}：{page.title or page.final_url[:80]}"[:500],
            description=hit.excerpt,
            published_at=record.published_at,
            collected_at=datetime.now(timezone.utc),
            confidence=hit.confidence,
            reliability_score=_source_score(db, record.source_id),
            status="VALID",
            fact_or_inference="FACT",
            payload_json={"extractor": "rule_engine_v1", "excerpt": hit.excerpt},
        )
        db.add(signal)
        db.flush()
        signals.append(signal)
    if signals:
        write_audit(db, "CREATE", "signal", signals[0].id, {"count": len(signals), "via": "rule_engine", "source_record_id": record.id})
    return signals


def ingest_url(db: Session, url: str, note: str = "") -> "IngestResult":
    """手动 URL 采集编排（T03 起统一走 CollectorAdapter，与数据源采集同一套逻辑）。

    Adapter 抓取 → 空正文拒绝 → persist_collected（去重/版本化/企业关联/规则 Signal）
    → 可选 LLM 增强（未配置不阻塞）。
    """
    from app.collectors import ManualUrlCollector
    from app.services.collection_engine import persist_collected

    manual_source = get_manual_source(db)
    adapter = ManualUrlCollector(manual_source, {"url": url})
    adapter.validate_config()
    items = adapter.build_records()
    item = items[0] if items else None
    if item is None:
        raise extractor.URLSafetyError("采集器未返回任何结果")
    if item.parse_status == "FAILED" or (not (item.raw_text or "").strip() and not (item.title or "").strip()):
        if item.parse_status == "FAILED" and item.error_message and "正文" not in item.error_message:
            # 网络 / HTTP 失败（含 401/403 访问受限不绕过）→ 502
            raise RuntimeError(item.error_message)
        raise extractor.URLSafetyError(item.error_message or "页面无可提取的有效正文内容，拒绝入库")

    if note:
        item.extra["note"] = note
    record, outcome = persist_collected(db, manual_source, item)

    company = db.get(Company, record.company_id) if record.company_id else None
    result = IngestResult(
        source_id=manual_source.id,
        source_record_id=record.id,
        company_id=company.id if company else None,
        llm_configured=False,
        duplicate=(outcome == "SKIPPED_UNCHANGED"),
    )

    if outcome == "SKIPPED_UNCHANGED":
        existing_signals = db.scalars(select(Signal).where(Signal.source_record_id == record.id)).all()
        result.signal_ids = [s.id for s in existing_signals]
        result.message = "duplicate_record_reused"
        db.commit()
        return result

    if company is not None:
        existing = db.scalars(select(Signal).where(Signal.source_record_id == record.id)).all()
        result.signal_ids = [s.id for s in existing]

        adapter_llm = get_llm_adapter()
        if adapter_llm is not None:
            result.llm_configured = True
            insights = adapter_llm.extract_signal(db, item.title or "", item.raw_text or "", "source_record", record.id)
            for insight in insights:
                signal = Signal(
                    company_id=company.id,
                    source_record_id=record.id,
                    signal_type="NEW_PRODUCT",
                    title=insight.title[:500],
                    description=insight.inference,
                    published_at=record.published_at,
                    collected_at=datetime.now(timezone.utc),
                    confidence=insight.confidence,
                    reliability_score=manual_source.reliability_score,
                    status="VALID",
                    fact_or_inference="FACT",
                    payload_json={"extractor": "llm", "evidence_excerpt": insight.evidence_excerpt},
                )
                db.add(signal)
                db.flush()
                result.signal_ids.append(signal.id)
            signals_text = "\n".join(f"- {s.title}" for s in existing) or (item.raw_text or "")[:4000]
            pain_insights = adapter_llm.infer_pain_point(db, company.company_name, signals_text, "company", company.id)
            for insight in pain_insights:
                pain = PainPoint(
                    company_id=company.id,
                    category="AI_INFERRED",
                    description=insight.title,
                    confidence=insight.confidence,
                    reason=insight.inference,
                    status="INFERRED",
                )
                db.add(pain)
                db.flush()
                db.add(PainPointEvidence(pain_point_id=pain.id, source_record_id=record.id, evidence_excerpt=insight.evidence_excerpt))
                result.pain_point_ids.append(pain.id)
            result.message = "llm_enriched"

    db.commit()
    if not result.message:
        result.message = "ingested" if outcome == "CREATED" else "new_version_saved"
    return result
