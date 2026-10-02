"""PainAnalyzer —— PainPoint 必须是"推断"（T05）。

- 事实（Signal/Evidence）与推断（PainPoint）严格分离：PainPoint.status=INFERRED，
  reasoning_summary 说明由哪些真实 Signal 推断；
- CONFIRMED 只能来自人工确认/客户访谈/真实 Interaction，AI 不得升级；
- 分类对齐 PAIN_CATEGORIES 枚举（17 类）；同企业同分类在窗口内复用既有 PainPoint（追加证据）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers.opportunity.bundles import BundleDraft
from app.analyzers.opportunity.context import CompanyAnalysisContext, SignalContext
from app.core.constants import PAIN_CATEGORIES
from app.models.pain_point import PainPoint, PainPointEvidence

# 信号类型 → Pain 分类（规则表，可解释）
SIGNAL_PAIN_MAP: dict[str, list[str]] = {
    "SALES_HIRING": ["CUSTOMER_ACQUISITION", "SALES_EFFICIENCY"],
    "HIRING": ["RECRUITMENT"],
    "AI_HIRING": ["AI_TRANSFORMATION"],
    "TECH_HIRING": ["DIGITAL_TRANSFORMATION"],
    "CUSTOMER_SERVICE_HIRING": ["CUSTOMER_SERVICE", "RECRUITMENT"],
    "FINANCE_HIRING": ["FINANCE_EFFICIENCY", "RECRUITMENT"],
    "FUNDING": ["CUSTOMER_ACQUISITION"],
    "EXPANSION": ["CUSTOMER_ACQUISITION"],
    "OVERSEAS_EXPANSION": ["OVERSEAS_EXPANSION", "CUSTOMER_ACQUISITION"],
    "NEW_MARKET": ["CUSTOMER_ACQUISITION"],
    "NEW_PRODUCT": ["CUSTOMER_ACQUISITION"],
    "PROCUREMENT": ["PROCUREMENT"],
    "TENDER": ["PROCUREMENT"],
    "SUPPLIER_SEARCH": ["SUPPLIER_MANAGEMENT", "PROCUREMENT"],
    "CRM_DEMAND": ["SALES_EFFICIENCY", "CUSTOMER_ACQUISITION"],
    "ERP_DEMAND": ["PROCESS_AUTOMATION", "DATA_MANAGEMENT"],
    "AI_DEMAND": ["AI_TRANSFORMATION"],
    "AUTOMATION_DEMAND": ["PROCESS_AUTOMATION"],
    "DIGITAL_TRANSFORMATION": ["DIGITAL_TRANSFORMATION"],
    "AI_TRANSFORMATION": ["AI_TRANSFORMATION"],
    "CUSTOMER_COMPLAINT": ["CUSTOMER_SERVICE"],
    "COST_PRESSURE": ["COST_REDUCTION"],
    "EFFICIENCY_PROBLEM": ["PROCESS_AUTOMATION", "SALES_EFFICIENCY"],
    "MANUAL_WORK": ["PROCESS_AUTOMATION"],
    "DATA_PROBLEM": ["DATA_MANAGEMENT"],
}

_PAIN_LABEL = {k: v for k, v in PAIN_CATEGORIES.items()}
# 复用窗口：同企业同分类 PainPoint 在该天数内合并证据，不重复新建
PAIN_REUSE_WINDOW_DAYS = 30


@dataclass
class PainInference:
    category: str
    description: str
    confidence: int
    reasoning_summary: str
    signal_ids: list[str] = field(default_factory=list)


def infer_pains_from_signals(ctx: CompanyAnalysisContext, bundle: BundleDraft | None = None) -> list[PainInference]:
    """从真实 Signal 推断 PainPoint 候选（纯规则，可解释）。"""
    category_signals: dict[str, list[SignalContext]] = {}
    for sc in ctx.signals:
        for pain in SIGNAL_PAIN_MAP.get(sc.signal.signal_type, []):
            category_signals.setdefault(pain, []).append(sc)
    # 组合规则显式指向的分类：把组合成员信号也纳入（组合本身即证据）
    if bundle is not None:
        for pain in bundle.pain_categories:
            for sid in bundle.signal_ids:
                for sc in ctx.signals:
                    if sc.signal.id == sid and sc not in category_signals.setdefault(pain, []):
                        category_signals[pain].append(sc)

    inferences: list[PainInference] = []
    for category, scs in category_signals.items():
        scs = sorted(scs, key=lambda s: s.signal.confidence, reverse=True)
        top = scs[0]
        signal_ids = [s.signal.id for s in scs]
        # 置信度：最强信号置信度为主，多信号印证 + 密度加成
        confidence = top.signal.confidence
        if len(set(signal_ids)) >= 2:
            confidence = min(95, confidence + 8)
        if ctx.signal_count_30d >= 3:
            confidence = min(95, confidence + 4)
        evidence_titles = "；".join(
            f"「{(s.signal.fact_summary or s.signal.title)[:60]}」" for s in scs[:3]
        )
        description = (
            f"可能存在{_PAIN_LABEL.get(category, category)}方面的业务压力："
            f"基于 {len(set(signal_ids))} 条真实商业信号推断。"
        )
        reasoning = (
            f"支持信号：{evidence_titles}。"
            f"该结论为 AI 推断（INFERENCE），原文事实以关联 Signal 的 Evidence 为准。"
        )
        inferences.append(PainInference(
            category=category,
            description=description,
            confidence=confidence,
            reasoning_summary=reasoning,
            signal_ids=signal_ids,
        ))
    inferences.sort(key=lambda p: p.confidence, reverse=True)
    return inferences[:5]


def upsert_pain_point(db: Session, ctx: CompanyAnalysisContext, inference: PainInference, *, now: datetime | None = None) -> PainPoint:
    """把推断落库：同企业同分类在窗口内复用（追加证据与更高置信度），否则新建 INFERRED。"""
    now = now or datetime.now(timezone.utc)
    existing = db.scalars(
        select(PainPoint).where(
            PainPoint.company_id == ctx.company.id,
            PainPoint.category == inference.category,
            PainPoint.status.in_(["INFERRED", "REVIEWED"]),
        )
    ).all()
    target: PainPoint | None = None
    for pain in existing:
        anchor = pain.updated_at or pain.created_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if now - anchor <= timedelta(days=PAIN_REUSE_WINDOW_DAYS):
            target = pain
            break

    if target is None:
        target = PainPoint(
            company_id=ctx.company.id,
            market_id=ctx.company.markets[0].id if ctx.company.markets else None,
            category=inference.category,
            description=inference.description,
            confidence=inference.confidence,
            reason=inference.reasoning_summary,
            status="INFERRED",
        )
        db.add(target)
        db.flush()
    else:
        target.confidence = max(target.confidence, inference.confidence)
        target.reason = inference.reasoning_summary
        if not target.description:
            target.description = inference.description

    existing_signal_ids = {
        row.signal_id for row in db.scalars(
            select(PainPointEvidence).where(PainPointEvidence.pain_point_id == target.id)
        ).all()
    }
    for sc in ctx.signals:
        if sc.signal.id not in inference.signal_ids or sc.signal.id in existing_signal_ids:
            continue
        excerpt = (sc.evidences[0].quoted_text if sc.evidences else None) or sc.signal.fact_summary or sc.signal.title
        db.add(PainPointEvidence(
            pain_point_id=target.id,
            signal_id=sc.signal.id,
            source_record_id=sc.signal.source_record_id,
            evidence_excerpt=(excerpt or "")[:500],
        ))
    return target
