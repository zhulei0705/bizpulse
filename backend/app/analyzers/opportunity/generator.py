"""OpportunityGenerator —— 商业机会判断编排（T05）。

流程：Company → Approved Signals → Signal Bundles → Pain/Intent/Budget/Urgency/
AgentFit/Reachability/Evidence 分析 → ScoreEngine → EvidenceGate → OpportunityCandidate。

铁律：
- 进入条件：Approved Signal ≥ 1 且 Evidence ≥ 1（配置化），否则跳过；
- 无 Evidence 不能生成正式 Opportunity（EvidenceGate 在候选转正式时强制执行）；
- V1 全部候选默认 REVIEW，不自动 APPROVED；
- LLM 只产出结构化解释（pain/solution/why_now/risk/validation_questions），
  insufficient_evidence=true 时候选降为 NEED_MORE_EVIDENCE；分数永远由代码计算；
- 输入 hash 相同跳过重复分析；同指纹候选窗口内更新不新建。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers.opportunity.agent_fit import compute_agent_fit
from app.analyzers.opportunity.budget import compute_budget
from app.analyzers.opportunity.bundles import BundleDraft, build_signal_bundles
from app.analyzers.opportunity.context import CompanyAnalysisContext, load_company_context
from app.analyzers.opportunity.dedup import (
    compute_analysis_input_hash,
    compute_candidate_fingerprint,
    find_active_candidate,
    find_finalized_candidate,
    find_latest_candidate_with_hash,
)
from app.analyzers.opportunity.evidence import compute_evidence_score
from app.analyzers.opportunity.intent import compute_intent
from app.analyzers.opportunity.pain import infer_pains_from_signals, upsert_pain_point
from app.analyzers.opportunity.reachability import compute_reachability
from app.analyzers.opportunity.urgency import compute_urgency
from app.analyzers import prompts
from app.core.config import settings
from app.core.constants import PAIN_CATEGORIES
from app.llm import get_llm_adapter
from app.models.company import Company
from app.models.opportunity_candidate import OpportunityCandidate, SignalBundle
from app.models.signal import Signal
from app.services.audit import write_audit
from app.services.scoring import OpportunityScoreInput, calculate_opportunity_score

logger = logging.getLogger(__name__)


@dataclass
class GeneratorStats:
    company_id: str
    status: str = "SKIPPED"  # ANALYZED / SKIPPED
    reason: str | None = None
    candidates_created: int = 0
    candidates_updated: int = 0
    need_more_evidence: int = 0
    bundles: int = 0
    llm_used: bool = False
    errors: list[str] = field(default_factory=list)


# Pain 分类 → 解决方案假设（永远是 SOLUTION_HYPOTHESIS）
SOLUTION_HYPOTHESES: dict[str, str] = {
    "CUSTOMER_ACQUISITION": "智能获客服务（AI 线索挖掘与筛选）",
    "SALES_EFFICIENCY": "AI 销售效率工具（客户跟进自动化）",
    "LEAD_SHORTAGE": "精准线索获取服务",
    "OVERSEAS_EXPANSION": "海外获客自动化服务",
    "CUSTOMER_SERVICE": "智能客服自动化（Agent 客服）",
    "RECRUITMENT": "招聘流程自动化工具",
    "FINANCE_EFFICIENCY": "财务流程自动化（对账/报表 Agent）",
    "INVOICE_AUTOMATION": "发票识别与自动化处理",
    "PROCUREMENT": "采购信息聚合与流程自动化",
    "SUPPLIER_MANAGEMENT": "供应商管理数字化工具",
    "DATA_MANAGEMENT": "数据治理与系统集成服务",
    "AI_TRANSFORMATION": "AI 落地咨询与实施服务",
    "DIGITAL_TRANSFORMATION": "数字化升级实施服务",
    "PROCESS_AUTOMATION": "流程自动化（RPA / Agent）",
    "COMPLIANCE": "合规自动化工具",
    "COST_REDUCTION": "降本增效自动化方案",
    "OTHER": "定制自动化方案",
}

# Pain 分类 → 默认验证问题（AI 可生成问题，事实不能；客户访谈使用）
VALIDATION_QUESTIONS: dict[str, list[str]] = {
    "CUSTOMER_ACQUISITION": [
        "当前获客主要通过哪些渠道？各渠道的成本和转化如何？",
        "销售团队每周花费多少时间寻找和筛选潜在客户？",
        "是否已经购买过第三方获客/企业数据工具？效果如何？",
    ],
    "OVERSEAS_EXPANSION": [
        "海外销售团队目前每周有多少时间用于寻找海外潜在客户？",
        "海外线索主要来自哪些渠道（展会/平台/自有网站）？",
        "是否已经使用海外获客相关工具或服务？",
    ],
    "SALES_EFFICIENCY": [
        "销售跟进客户的主要痛点是哪个环节（找线索/初筛/跟进）？",
        "目前是否使用 CRM？使用中的最大不满是什么？",
    ],
    "CUSTOMER_SERVICE": [
        "客服团队当前的人均接待量是多少？高峰期如何应对？",
        "重复性问题咨询占比大概多少？是否使用过智能客服？",
    ],
    "FINANCE_EFFICIENCY": [
        "财务对账/报表目前的人工处理时长是多少？",
        "哪些财务流程最耗人力？是否评估过自动化方案？",
    ],
    "PROCESS_AUTOMATION": [
        "目前最耗人力的重复性流程是什么？",
        "是否评估过 RPA 或 Agent 自动化方案？顾虑是什么？",
    ],
    "DATA_MANAGEMENT": [
        "目前数据分散在哪些系统？打通的主要障碍是什么？",
        "数据问题对业务决策的实际影响有哪些？",
    ],
    "AI_TRANSFORMATION": [
        "目前 AI 在哪些业务环节有落地尝试？效果如何？",
        "推进 AI 落地的主要障碍（预算/人才/场景）是什么？",
    ],
    "COST_REDUCTION": [
        "当前成本压力最大的环节是哪里？",
        "是否已经在评估降本相关的自动化/外包方案？",
    ],
}
_GENERIC_QUESTIONS = [
    "该业务问题目前由哪个团队负责？投入多少人力？",
    "是否已经尝试过相关解决方案？效果与不满是什么？",
    "如果这类问题能自动化，预期节省多少人力时间？",
]


def _validation_questions(pain_category: str | None) -> list[str]:
    return list(VALIDATION_QUESTIONS.get(pain_category or "", _GENERIC_QUESTIONS))[:4]


def _build_signals_payload(ctx: CompanyAnalysisContext) -> str:
    """给 LLM 的事实输入：仅真实 Signal/Evidence 原文。"""
    lines: list[str] = []
    for sc in ctx.signals:
        signal = sc.signal
        lines.append(
            f"- [{signal.signal_type}] {signal.fact_summary or signal.title}"
            f"（置信度 {signal.confidence}，来源等级 {sc.source_grade}，"
            f"时间 {signal.published_at.date().isoformat() if signal.published_at else '未知'}）"
        )
        for evidence in sc.evidences[:2]:
            lines.append(f"    原文证据：{(evidence.quoted_text or '')[:200]}")
    return "\n".join(lines)


def _candidate_status(evidence_result, bundle_confidence: int, llm_result: dict | None) -> str:
    """候选状态：V1 不自动批准。单条弱证据 / 证据分过低 / LLM 判定证据不足 → NEED_MORE_EVIDENCE。"""
    if llm_result and llm_result.get("insufficient_evidence") is True:
        return "NEED_MORE_EVIDENCE"
    single_weak = len(evidence_result.refs) == 1 and evidence_result.refs[0].grade not in {"A", "B"}
    if single_weak or evidence_result.score < settings.evidence_gate_threshold and len(evidence_result.refs) <= 1:
        return "NEED_MORE_EVIDENCE"
    return "REVIEW"


def analyze_company_opportunities(db: Session, company_id: str, *, force: bool = False) -> GeneratorStats:
    stats = GeneratorStats(company_id=company_id)
    ctx = load_company_context(db, company_id)
    if ctx is None:
        stats.reason = "company_not_found"
        return stats

    # 1) 进入条件：Approved Signal ≥ 1 且 Evidence ≥ 1（NO_OPPORTUNITY_WITHOUT_SIGNAL/EVIDENCE）
    if len(ctx.signals) < settings.opportunity_min_approved_signals:
        stats.reason = f"approved_signals({len(ctx.signals)}) < {settings.opportunity_min_approved_signals}"
        return stats
    if ctx.evidence_count < settings.opportunity_min_evidences:
        stats.reason = f"evidences({ctx.evidence_count}) < {settings.opportunity_min_evidences}"
        return stats

    # 2) 输入 hash：完全相同则跳过（不每天重复分析相同内容）
    signal_ids = [s.signal.id for s in ctx.signals]
    fingerprints = [s.signal.signal_fingerprint or s.signal.id for s in ctx.signals]
    input_hash = compute_analysis_input_hash(company_id, signal_ids, fingerprints, prompts.OPPORTUNITY_GENERATOR_V1)
    if not force:
        latest = find_latest_candidate_with_hash(db, company_id, input_hash)
        if latest is not None:
            stats.reason = "analysis_input_unchanged"
            return stats
    stats.status = "ANALYZED"

    now = datetime.now(timezone.utc)
    llm_adapter = get_llm_adapter()
    if llm_adapter is not None:
        stats.llm_used = True

    # 3) Signal Bundles（组合规则可解释；无组合命中时用单信号兜底）
    drafts = build_signal_bundles(ctx)
    stats.bundles = len(drafts)

    def persist_bundle(bundle: BundleDraft) -> SignalBundle:
        existing = db.scalar(
            select(SignalBundle).where(
                SignalBundle.company_id == company_id,
                SignalBundle.bundle_type == bundle.bundle_type,
            ).order_by(SignalBundle.updated_at.desc()).limit(1)
        )
        if existing is not None:
            existing.signal_ids_json = bundle.signal_ids
            existing.signal_types_json = bundle.signal_types
            existing.pain_categories = bundle.pain_categories
            existing.confidence = bundle.confidence
            existing.signal_count_7d = ctx.signal_count_7d
            existing.signal_count_30d = ctx.signal_count_30d
            existing.signal_count_90d = ctx.signal_count_90d
            existing.explanation_json = bundle.explanation
            existing.first_signal_at = bundle.first_signal_at
            existing.last_signal_at = bundle.last_signal_at
            return existing
        row = SignalBundle(
            company_id=company_id,
            bundle_type=bundle.bundle_type,
            signal_ids_json=bundle.signal_ids,
            signal_types_json=bundle.signal_types,
            pain_categories=bundle.pain_categories,
            confidence=bundle.confidence,
            time_window_days=settings.opportunity_dedup_window_days,
            signal_count_7d=ctx.signal_count_7d,
            signal_count_30d=ctx.signal_count_30d,
            signal_count_90d=ctx.signal_count_90d,
            explanation_json=bundle.explanation,
            first_signal_at=bundle.first_signal_at,
            last_signal_at=bundle.last_signal_at,
        )
        db.add(row)
        db.flush()
        return row

    # 4) 单信号兜底（无组合命中时）：最强"当前"信号 → 其指向的 Pain 分类。
    # T08.2 门（任务书二十三/二十六）：历史信号（已中标等）不得单独触发当前机会；
    # 全部为历史信号时不生成候选（历史采购不是当下购买窗口）。
    if not drafts:
        from app.analyzers.opportunity.bundles import _is_current_signal

        current_signals = [s for s in ctx.signals if _is_current_signal(s.signal)]
        if not current_signals:
            stats.reason = "only_historical_signals（全部已批准信号为历史事件，不生成当前机会）"
            return stats
        top_signal = max(current_signals, key=lambda s: s.signal.confidence)
        from app.analyzers.opportunity.pain import SIGNAL_PAIN_MAP
        fallback_pains = SIGNAL_PAIN_MAP.get(top_signal.signal.signal_type, ["OTHER"])
        drafts = [BundleDraft(
            bundle_type="SINGLE_SIGNAL",
            signal_ids=[top_signal.signal.id],
            signal_types=[top_signal.signal.signal_type],
            pain_categories=fallback_pains[:2],
            confidence=max(SINGLE_SIGNAL_CONFIDENCE_FLOOR, top_signal.signal.confidence - 10),
            explanation={
                "rule": "单信号候选（无组合命中）",
                "rationale": "仅单一信号，置信度受限，需更多证据",
                "core_types": [top_signal.signal.signal_type],
                "support_types": [],
                "support_count": 0,
                "signal_count_7d": ctx.signal_count_7d,
                "signal_count_30d": ctx.signal_count_30d,
                "signal_count_90d": ctx.signal_count_90d,
            },
            first_signal_at=top_signal.newest_evidence_at,
            last_signal_at=top_signal.newest_evidence_at,
        )]

    intent = compute_intent(ctx, now=now)
    budget = compute_budget(ctx, db, now=now)
    urgency = compute_urgency(ctx, now=now)
    reachability = compute_reachability(ctx)
    evidence = compute_evidence_score(ctx, now=now)

    skipped_finalized = 0
    for draft in drafts:
        bundle_row = persist_bundle(draft) if draft.bundle_type != "SINGLE_SIGNAL" else None
        pains = infer_pains_from_signals(ctx, draft)
        if not pains:
            continue
        pain_inference = pains[0]
        pain_point = upsert_pain_point(db, ctx, pain_inference, now=now)

        agent_fit = compute_agent_fit(ctx, pain_inference.category)
        reasons = {
            "pain": pain_inference.reasoning_summary and [pain_inference.reasoning_summary] or [],
            "budget": budget.reasons,
            "intent": intent.reasons,
            "urgency": urgency.reasons,
            "agent_fit": agent_fit.reasons,
            "reachability": reachability.reasons,
            "evidence": evidence.reasons,
        }
        scored = calculate_opportunity_score(OpportunityScoreInput(
            pain=pain_inference.confidence,
            budget=budget.score,
            intent=intent.score,
            urgency=urgency.score,
            agent_fit=agent_fit.score,
            reachability=reachability.score,
            evidence=evidence.score,
        ), reasons=reasons)

        # LLM 解释（可选）：只产出结构化解释，分数仍由代码决定
        llm_result: dict | None = None
        if llm_adapter is not None:
            payload = _build_signals_payload(ctx)
            payload += f"\n\n代码计算分数：pain={pain_inference.confidence} budget={budget.score} intent={intent.score} urgency={urgency.score} agent_fit={agent_fit.score} reachability={reachability.score} evidence={evidence.score}"
            llm_result = llm_adapter.generate_opportunity_v1(db, ctx.company.company_name, payload, "company", company_id)

        # 风险备注：诚实列出负面因素
        risk_notes: list[str] = []
        if budget.budget_level == "UNKNOWN":
            risk_notes.append("尚无公开预算/金额证据，预算能力未知（Budget 不猜测）")
        if intent.extra.get("direct_purchase", 0) == 0:
            risk_notes.append("未发现公开采购等直接购买信号，购买意图为推断")
        if len(evidence.refs) <= 1:
            risk_notes.append("证据数量不足（≤1 条），存在误判可能")
        if reachability.score < 40:
            risk_notes.append("缺少公开触达渠道")
        for item in evidence.contradicting:
            risk_notes.append(f"矛盾证据：{item.excerpt[:80]}")

        solution_category = SOLUTION_HYPOTHESES.get(pain_inference.category, SOLUTION_HYPOTHESES["OTHER"])
        pain_label = PAIN_CATEGORIES.get(pain_inference.category, pain_inference.category)
        newest = ctx.newest_signal_at
        age_days = (now - newest).days if newest else None
        why_now_rule = (
            f"最近 30 天出现 {ctx.signal_count_30d} 条相关信号（7 天内 {ctx.signal_count_7d} 条），"
            f"最新信号：{ctx.signals[0].signal.title[:80]}"
            + (f"（{age_days} 天前）" if age_days is not None else "")
        )
        if llm_result and llm_result.get("why_now"):
            why_now = str(llm_result["why_now"])[:1000]
        else:
            why_now = why_now_rule

        fingerprint = compute_candidate_fingerprint(
            company_id, pain_inference.category, solution_category,
            published_at=draft.last_signal_at, collected_at=now,
        )
        existing_candidate = find_active_candidate(db, fingerprint)
        if existing_candidate is None and find_finalized_candidate(db, fingerprint) is not None:
            # 同指纹候选已终态（已转正式机会/已批准/已拒绝）：人工决策优先，不重建
            # （fingerprint 全局唯一，直接 INSERT 会撞 UNIQUE 约束）
            skipped_finalized += 1
            continue

        confidence = bundle_confidence_for(draft.confidence, llm_result)

        values = dict(
            company_id=company_id,
            market_id=ctx.company.markets[0].id if ctx.company.markets else None,
            bundle_id=bundle_row.id if bundle_row else None,
            pain_point_id=pain_point.id,
            title=f"{pain_label}机会：{ctx.company.company_name}",
            problem_hypothesis=pain_inference.description + " " + pain_inference.reasoning_summary,
            solution_hypothesis=f"【SOLUTION_HYPOTHESIS】{solution_category} —— 基于信号推断的可能方案，需人工验证，不代表客户已有明确采购需求。",
            value_hypothesis="【VALUE_HYPOTHESIS】潜在价值方向：提高获客/业务效率、减少重复人工、降低时间成本（未经客户验证，不承诺 ROI 数字）。",
            trigger_summary="；".join(
                sc.signal.title for sc in ctx.signals if sc.signal.id in draft.signal_ids
            )[:1000],
            why_now=why_now,
            evidence_summary=(
                f"共 {len(evidence.refs)} 条原文证据（最高来源等级 {ctx.best_source_grade}）；"
                f"矛盾证据 {len(evidence.contradicting)} 条。"
            ),
            recommended_next_action=next_action_for(evidence.score, reachability.score),
            signal_ids_json=draft.signal_ids,
            pain_category=pain_inference.category,
            solution_category=solution_category,
            pain_score=pain_inference.confidence,
            budget_score=budget.score,
            intent_score=intent.score,
            urgency_score=urgency.score,
            agent_fit_score=agent_fit.score,
            reachability_score=reachability.score,
            evidence_score=evidence.score,
            total_score=scored.score,
            grade=scored.grade,
            grade_cap_reason=scored.grade_cap_reason,
            confidence=confidence,
            score_breakdown_json=scored.breakdown,
            risk_notes=risk_notes,
            validation_questions=(llm_result.get("validation_questions") if llm_result else None) or _validation_questions(pain_inference.category),
            evidence_refs_json=[{
                "signal_id": r.signal_id,
                "source_record_id": r.source_record_id,
                "polarity": r.polarity,
                "grade": r.grade,
                "excerpt": r.excerpt,
                "url": r.url,
            } for r in evidence.refs],
            contradicting_evidence_json=[{
                "signal_id": r.signal_id,
                "source_record_id": r.source_record_id,
                "polarity": r.polarity,
                "grade": r.grade,
                "excerpt": r.excerpt,
            } for r in evidence.contradicting],
            status=_candidate_status(evidence, draft.confidence, llm_result),
            generated_by="LLM" if (llm_result and not llm_result.get("insufficient_evidence")) else "RULE",
            prompt_version=prompts.OPPORTUNITY_GENERATOR_V1 if llm_result else None,
            analysis_input_hash=input_hash,
            fingerprint=fingerprint,
            last_signal_at=draft.last_signal_at or ctx.newest_signal_at,
            last_evidence_at=draft.last_signal_at or ctx.newest_signal_at,
        )

        if existing_candidate is not None:
            for key, value in values.items():
                setattr(existing_candidate, key, value)
            # 证据补强后从 NEED_MORE_EVIDENCE 回到 REVIEW
            if existing_candidate.status == "REVIEW" or evidence.score >= settings.evidence_gate_threshold:
                existing_candidate.status = values["status"] if values["status"] == "NEED_MORE_EVIDENCE" else "REVIEW"
            stats.candidates_updated += 1
            candidate = existing_candidate
        else:
            candidate = OpportunityCandidate(**values)
            db.add(candidate)
            db.flush()
            stats.candidates_created += 1
        if candidate.status == "NEED_MORE_EVIDENCE":
            stats.need_more_evidence += 1

    if skipped_finalized and not stats.candidates_created and not stats.candidates_updated:
        stats.reason = f"candidates_finalized({skipped_finalized})"
    write_audit(db, "OPPORTUNITY_ANALYZED", "company", company_id, {
        "bundles": [d.bundle_type for d in drafts],
        "candidates_created": stats.candidates_created,
        "candidates_updated": stats.candidates_updated,
        "candidates_skipped_finalized": skipped_finalized,
        "llm_used": stats.llm_used,
        "analysis_input_hash": input_hash,
    })
    db.commit()
    return stats


SINGLE_SIGNAL_CONFIDENCE_FLOOR = 40


def bundle_confidence_for(bundle_confidence: int, llm_result: dict | None) -> int:
    """候选置信度：代码计算的组合置信度为主；LLM 置信度仅作参考混合（可解释）。"""
    if llm_result is None:
        return bundle_confidence
    try:
        llm_conf = max(0, min(int(llm_result.get("confidence", 0)), 100))
    except (TypeError, ValueError):
        return bundle_confidence
    return int(round(bundle_confidence * 0.6 + llm_conf * 0.4))


def next_action_for(evidence_score: int, reachability_score: int) -> str:
    if evidence_score < settings.evidence_gate_threshold:
        return "RESEARCH"
    if reachability_score < 40:
        return "FIND_CONTACT"
    return "MANUAL_REVIEW"


def analyze_companies_batch(db: Session, *, limit: int = 50) -> dict:
    """批量机会分析：只分析有已批准 Signal 的企业；输入 hash 未变的自动跳过。"""
    job = None
    from app.models.job import CollectionJob
    job = CollectionJob(name="批量机会分析", job_type="ANALYZE_OPPORTUNITY", status="RUNNING", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    company_ids = [row[0] for row in db.execute(
        select(Signal.company_id).where(Signal.status == "APPROVED", Signal.company_id.is_not(None))
        .group_by(Signal.company_id).limit(limit)
    ).all()]

    totals = {"total": len(company_ids), "analyzed": 0, "skipped": 0, "created": 0, "updated": 0, "need_more_evidence": 0, "failed": 0}
    run_log: list[dict] = []
    for company_id in company_ids:
        try:
            stats = analyze_company_opportunities(db, company_id)
            if stats.status == "ANALYZED":
                totals["analyzed"] += 1
                totals["created"] += stats.candidates_created
                totals["updated"] += stats.candidates_updated
                totals["need_more_evidence"] += stats.need_more_evidence
            else:
                totals["skipped"] += 1
            run_log.append({"company_id": company_id, "status": stats.status, "reason": stats.reason,
                            "created": stats.candidates_created, "updated": stats.candidates_updated})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            totals["failed"] += 1
            run_log.append({"company_id": company_id, "error": str(exc)[:200]})

    stale = mark_stale_opportunities(db)
    job.finished_at = datetime.now(timezone.utc)
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds() if job.started_at else None
    job.items_found = totals["total"]
    job.items_created = totals["created"]
    job.items_updated = totals["updated"]
    job.items_skipped = totals["skipped"]
    job.error_count = totals["failed"]
    job.status = "PARTIAL_SUCCESS" if totals["failed"] else "SUCCESS"
    job.run_log_json = run_log
    job.query = f"stats:{totals}; stale:{stale}"
    db.commit()
    return {"job_id": job.id, **totals, "stale_marked": stale}


def mark_stale_opportunities(db: Session, *, now: datetime | None = None) -> int:
    """机会过期：超过 stale_days 无新 Signal 的正式机会进入 STALE（期限配置化）。"""
    from app.models.opportunity import Opportunity
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.opportunity_stale_days)
    rows = db.scalars(
        select(Opportunity).where(
            Opportunity.status == "ACTIVE",
            Opportunity.stage.not_in(["WON", "REJECTED", "STALE"]),
        )
    ).all()
    marked = 0
    for opp in rows:
        anchor = opp.last_signal_at or opp.updated_at or opp.created_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if anchor < cutoff:
            opp.stage = "STALE"
            opp.stale_reason = f"超过 {settings.opportunity_stale_days} 天无新 Signal（最近：{anchor.date().isoformat()}）"
            write_audit(db, "OPPORTUNITY_STALE", "opportunity", opp.id, {"stale_reason": opp.stale_reason})
            marked += 1
    if marked:
        db.commit()
    return marked
