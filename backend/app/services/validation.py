"""T06 商业验证状态机与真实性约束（Service 层）。

原则：
- 状态只能反映真实发生的事：没有回复就是 NO_RESPONSE，AI 不得推测；
- 主流程不允许大跨度跳跃（NEW → WON 禁止），跳步必须人工 force + 说明；
- WON 需要真实合同金额；REJECTED 需要统一拒绝原因；报价金额不是收入；
- 联系人 VERIFIED_PUBLIC 必须有真实公开来源。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    CONTACT_VERIFICATION_STATUSES,
    EXPERIMENT_REJECT_REASONS,
    INTERACTION_CHANNELS,
    INTERACTION_DIRECTIONS,
    INTERACTION_TYPES,
    OPPORTUNITY_STAGES,
    QUOTE_STATUSES,
    REPLY_CATEGORIES,
    TARGET_FLOW,
    TARGET_STATUS_RANK,
    VALIDATING_STAGES,
)
from app.models.experiment import ExperimentOutcome, ExperimentTarget, Interaction
from app.models.opportunity import Opportunity, OpportunityFeedback
from app.models.pain_point import PainPoint
from app.services.audit import write_audit

# Interaction 类型 → Target 应推进到的状态（真实行为驱动状态，AI 不改变状态）
INTERACTION_TYPE_TO_TARGET_STATUS: dict[str, str] = {
    "OUTREACH": "CONTACTED",
    "FOLLOW_UP": "CONTACTED",
    "REPLY": "REPLIED",
    "MEETING": "MEETING",
    "DEMO": "MEETING",
    "PROPOSAL": "QUOTED",
    "QUOTE": "QUOTED",
    "NEGOTIATION": "QUOTED",
    "PILOT": "PILOT",
    "CONTRACT": "WON",
    "PAYMENT": "WON",
    "REJECTION": "REJECTED",
}

# Interaction 类型 → Opportunity 阶段（同步推进验证流程）
INTERACTION_TYPE_TO_OPP_STAGE: dict[str, str] = {
    "OUTREACH": "CONTACTED",
    "FOLLOW_UP": "CONTACTED",
    "REPLY": "REPLIED",
    "MEETING": "MEETING",
    "DEMO": "MEETING",
    "PROPOSAL": "QUOTED",
    "QUOTE": "QUOTED",
    "NEGOTIATION": "QUOTED",
    "PILOT": "PILOT",
    "CONTRACT": "WON",
    "PAYMENT": "WON",
}

# Interaction 类型 → 观察到的真实购买意图（与预测 intent_score 严格区分）
INTERACTION_TYPE_TO_OBSERVED_INTENT: dict[str, str] = {
    "REPLY": "REPLIED",
    "MEETING": "MEETING_BOOKED",
    "DEMO": "MEETING_BOOKED",
    "QUOTE": "QUOTE_REQUESTED",
    "PILOT": "PILOT_STARTED",
    "CONTRACT": "PILOT_STARTED",
    "REJECTION": "DECLINED",
}

# 每个 Interaction 类型允许的方向（反伪造：客户回复必须 INBOUND，我方触达必须 OUTBOUND）
INTERACTION_TYPE_DIRECTIONS: dict[str, set[str]] = {
    "RESEARCH": {"INTERNAL"},
    "NOTE": {"INTERNAL"},
    "OUTREACH": {"OUTBOUND"},
    "FOLLOW_UP": {"OUTBOUND"},
    "PROPOSAL": {"OUTBOUND"},
    "QUOTE": {"OUTBOUND"},
    "REPLY": {"INBOUND"},
    "REJECTION": {"INBOUND"},
    "MEETING": {"OUTBOUND", "INBOUND"},
    "DEMO": {"OUTBOUND", "INBOUND"},
    "NEGOTIATION": {"OUTBOUND", "INBOUND"},
    "PILOT": {"INTERNAL", "OUTBOUND", "INBOUND"},
    "CONTRACT": {"INTERNAL"},
    "PAYMENT": {"INBOUND", "INTERNAL"},
}

# 只有真实交易行为才能记录收入（报价 QUOTE 的金额永远是报价，不是收入）
REVENUE_ALLOWED_TYPES = {"CONTRACT", "PAYMENT"}
REJECT_REASON_ALLOWED_TYPES = {"REJECTION"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TransitionDenied(HTTPException):
    """状态流转被拒绝（422，带原因说明）。"""


# ---------------------------------------------------------------------------
# Target 状态机
# ---------------------------------------------------------------------------

def transition_target(
    db: Session,
    target: ExperimentTarget,
    new_status: str,
    *,
    note: str | None = None,
    reject_reason: str | None = None,
    contract_amount: Decimal | None = None,
    next_action: str | None = None,
    next_action_at: datetime | None = None,
    force: bool = False,
    actor: str = "local-user",
) -> ExperimentTarget:
    """验证目标企业状态流转（人工驱动；系统按真实 Interaction 建议状态）。

    规则：
    - 主流程（TARGET_FLOW）允许前进 1 步或任意后退；跳 2+ 步必须 force=True + note；
    - REJECTED 必须带统一拒绝原因（客户真实反馈；无回复只能 NO_RESPONSE）；
    - NO_RESPONSE 仅在已联系之后成立；
    - WON 必须提供真实合同金额（contract_amount > 0）；
    - 终态（WON/REJECTED/NO_RESPONSE）重新打开必须 force + note。
    """
    old_status = target.status
    if new_status not in {'PAUSED', 'REJECTED', 'NO_RESPONSE'} and target.opportunity_id:
        from app.models.opportunity import Opportunity
        from app.services.evidence_integrity import opportunity_issues
        opportunity=db.get(Opportunity,target.opportunity_id)
        if opportunity and opportunity_issues(db,opportunity):
            raise TransitionDenied(status_code=422,detail='INVALID_EVIDENCE：目标机会需要重新人工审核，禁止推进')
    if old_status == new_status:
        return target
    if new_status not in TARGET_STATUS_RANK and new_status not in {"REJECTED", "NO_RESPONSE", "PAUSED"}:
        raise TransitionDenied(status_code=422, detail=f"未知目标状态：{new_status}")

    old_rank = TARGET_STATUS_RANK.get(old_status)
    new_rank = TARGET_STATUS_RANK.get(new_status)

    if new_status == "REJECTED":
        if not reject_reason:
            raise TransitionDenied(status_code=422, detail="拒绝必须提供真实拒绝原因 reject_reason（客户明确反馈；无回复请使用 NO_RESPONSE）")
        if reject_reason not in EXPERIMENT_REJECT_REASONS:
            raise TransitionDenied(status_code=422, detail=f"reject_reason 必须是 {sorted(EXPERIMENT_REJECT_REASONS)} 之一")
        if reject_reason in {"NO_BUDGET", "PRICE_HIGH"} and old_rank is not None and old_rank < TARGET_STATUS_RANK["QUOTED"]:
            raise TransitionDenied(status_code=422, detail="未到报价阶段的拒绝不能归因于预算/价格（没有真实价格沟通）")
    elif new_status == "NO_RESPONSE":
        if old_rank is None or old_rank < TARGET_STATUS_RANK["CONTACTED"]:
            raise TransitionDenied(status_code=422, detail="只有已联系过的目标才能标记无回复（NO_RESPONSE）")
    elif new_status == "WON":
        if contract_amount is None or contract_amount <= 0:
            raise TransitionDenied(status_code=422, detail="标记成交必须提供真实合同金额 contract_amount（口头意向不算成交）")

    if old_rank is not None and new_rank is not None:
        forward_steps = new_rank - old_rank
        if forward_steps > 1 and not force:
            flow = TARGET_FLOW
            raise TransitionDenied(
                status_code=422,
                detail=(
                    f"不允许从 {old_status} 直接跳到 {new_status}（跳 {forward_steps} 步）。"
                    f"请按 {flow[old_rank]} → {flow[old_rank + 1]} 逐步推进并记录真实互动；"
                    f"确有必要时需 force=true 并附说明。"
                ),
            )
        if forward_steps > 1 and force and not note:
            raise TransitionDenied(status_code=422, detail="跳步推进（force=true）必须附 note 说明真实依据")
    if old_status in {"WON", "REJECTED", "NO_RESPONSE"} and not force:
        raise TransitionDenied(status_code=422, detail=f"该目标已终态（{old_status}），重新打开需要 force=true 并附说明")

    target.status = new_status
    if new_rank is not None:
        reached_rank = TARGET_STATUS_RANK.get(target.reached_stage, 0)
        if new_rank > reached_rank:
            target.reached_stage = new_status
    if reject_reason is not None:
        target.notes = ((target.notes or "") + f"\n[拒绝原因 {new_status}] {reject_reason}").strip()
    if next_action is not None:
        target.next_action = next_action
    if next_action_at is not None:
        target.next_action_at = next_action_at
    if new_status == "WON":
        target.next_action = target.next_action or "已成交"
    if note:
        target.notes = ((target.notes or "") + f"\n[{_now().date().isoformat()} {old_status}→{new_status}] {note}").strip()
    target.updated_at = _now()

    write_audit(db, "TARGET_STATUS_CHANGE", "experiment_target", target.id, {
        "experiment_id": target.experiment_id, "company_id": target.company_id,
        "before": old_status, "after": new_status,
        "reject_reason": reject_reason, "note": note, "force": force,
    })

    if new_status in {"WON", "REJECTED", "NO_RESPONSE"}:
        _write_outcome_and_feedback(
            db, target, new_status,
            reject_reason=reject_reason, contract_amount=contract_amount,
        )
    return target


def _write_outcome_and_feedback(
    db: Session,
    target: ExperimentTarget,
    final_status: str,
    *,
    reject_reason: str | None = None,
    contract_amount: Decimal | None = None,
) -> None:
    """终态：写 Outcome 快照 + Opportunity Feedback（预测 vs 真实；只积累，不训练）。"""
    now = _now()
    # actual_* 按目标到达过的最远漏斗阶段判定（状态本身是人工记录的真实事实）
    reached_rank = TARGET_STATUS_RANK.get(target.reached_stage, 0)
    actual_reply = reached_rank >= TARGET_STATUS_RANK["REPLIED"]
    actual_meeting = reached_rank >= TARGET_STATUS_RANK["MEETING"]
    actual_quote = reached_rank >= TARGET_STATUS_RANK["QUOTED"]
    actual_pilot = reached_rank >= TARGET_STATUS_RANK["PILOT"]
    actual_win = final_status == "WON"
    actual_revenue = float(contract_amount) if contract_amount else None

    outcome = db.scalar(select(ExperimentOutcome).where(ExperimentOutcome.target_id == target.id))
    if outcome is None:
        outcome = ExperimentOutcome(target_id=target.id, experiment_id=target.experiment_id, company_id=target.company_id, opportunity_id=target.opportunity_id)
        db.add(outcome)
    outcome.final_status = final_status
    outcome.won = actual_win
    outcome.contract_amount = contract_amount if actual_win else outcome.contract_amount
    outcome.currency = outcome.currency or "CNY"
    outcome.reject_reason = reject_reason or (None if actual_win else outcome.reject_reason)
    outcome.closed_at = now
    outcome.updated_at = now
    db.flush()

    write_audit(db, "EXPERIMENT_OUTCOME", "experiment_outcome", outcome.id, {
        "target_id": target.id, "final_status": final_status,
        "won": actual_win, "reject_reason": reject_reason,
    })

    # PainPoint 自动确认联动：interaction.confirm_pain 已显式处理，此处不自动升级（CONFIRMED 只能人工确认）

    if not target.opportunity_id:
        return
    opportunity = db.get(Opportunity, target.opportunity_id)
    if opportunity is None:
        return
    feedback = OpportunityFeedback(
        opportunity_id=opportunity.id,
        target_id=target.id,
        predicted_score=opportunity.total_score,
        predicted_grade=opportunity.grade,
        actual_reply=actual_reply,
        actual_meeting=actual_meeting,
        actual_quote=actual_quote,
        actual_pilot=actual_pilot,
        actual_win=actual_win,
        actual_revenue=actual_revenue,
        reject_reason=reject_reason,
        notes=f"final_status={final_status}; experiment={target.experiment_id}",
        feedback_at=now,
    )
    db.add(feedback)
    db.flush()
    write_audit(db, "OPPORTUNITY_FEEDBACK", "opportunity_feedback", feedback.id, {
        "opportunity_id": opportunity.id, "predicted_score": opportunity.total_score,
        "actual_win": actual_win, "reject_reason": reject_reason,
    })
    # 同步机会阶段与真实意图（WON/REJECTED/NO_RESPONSE 终态）
    stage_map = {"WON": "WON", "REJECTED": "REJECTED"}
    if final_status in stage_map and opportunity.stage not in {"STALE"}:
        opportunity.stage = stage_map[final_status]
    if final_status == "NO_RESPONSE":
        opportunity.observed_intent = "NO_RESPONSE"


# ---------------------------------------------------------------------------
# Opportunity 阶段流转
# ---------------------------------------------------------------------------

OPP_FLOW = ["NEW", "REVIEW", "READY", "CONTACTED", "REPLIED", "MEETING", "QUOTED", "PILOT", "WON"]


def validate_opportunity_stage_transition(
    db: Session,
    opportunity: Opportunity,
    new_stage: str,
    *,
    reject_reason: str | None = None,
    contract_amount: Decimal | None = None,
    force: bool = False,
    note: str | None = None,
) -> None:
    """机会验证阶段流转校验（Service 层保护；Kanban 拖动也走这里）。

    - 未人工审核通过（review_status != APPROVED）禁止进入验证阶段（READY 及之后）；
    - 主流程允许前进 1 步或后退；跳 2+ 步需要 force + note（人工确认）；
    - WON 必须提供真实合同金额；REJECTED 需要统一拒绝原因；
    - STALE 只能由系统过期清扫设置。
    """
    from app.core.constants import LEGACY_STAGE_MAP

    new_stage = LEGACY_STAGE_MAP.get(new_stage, new_stage)
    if new_stage in VALIDATING_STAGES or new_stage == 'READY':
        from app.services.evidence_integrity import opportunity_issues
        if opportunity_issues(db,opportunity):
            raise TransitionDenied(status_code=422,detail='INVALID_EVIDENCE：机会证据隔离，禁止推进')
    old_stage = opportunity.stage
    if old_stage == new_stage:
        return
    if new_stage == "STALE":
        raise TransitionDenied(status_code=422, detail="STALE 由系统按信号过期自动标记，不允许人工直接设置")
    if new_stage not in OPPORTUNITY_STAGES:
        raise TransitionDenied(status_code=422, detail=f"未知机会阶段：{new_stage}")

    if new_stage in VALIDATING_STAGES or new_stage in {"WON", "REJECTED"}:
        if opportunity.review_status != "APPROVED" and not force:
            raise TransitionDenied(status_code=422, detail="机会尚未人工审核通过（review_status != APPROVED），不能进入验证流程")

    old_rank = OPP_FLOW.index(old_stage) if old_stage in OPP_FLOW else None
    new_rank = OPP_FLOW.index(new_stage) if new_stage in OPP_FLOW else None
    if new_stage == "REJECTED":
        # 验证阶段的拒绝 = 客户真实拒绝，使用 T06 统一客户拒绝原因（与 T05 候选驳回原因区分）
        from app.core.constants import EXPERIMENT_REJECT_REASONS
        if not reject_reason:
            raise TransitionDenied(status_code=422, detail="拒绝机会必须提供真实拒绝原因 reject_reason（客户真实反馈；无回复只能 NO_RESPONSE）")
        if reject_reason not in EXPERIMENT_REJECT_REASONS:
            raise TransitionDenied(status_code=422, detail=f"reject_reason 必须是 {sorted(EXPERIMENT_REJECT_REASONS)} 之一")
    elif new_stage == "WON":
        if contract_amount is None or contract_amount <= 0:
            raise TransitionDenied(status_code=422, detail="标记成交必须提供真实合同金额 contract_amount（口头意向不算成交）")
    elif old_rank is not None and new_rank is not None:
        forward_steps = new_rank - old_rank
        if forward_steps > 1 and not force:
            raise TransitionDenied(
                status_code=422,
                detail=f"不允许从 {old_stage} 直接跳到 {new_stage}（跳 {forward_steps} 步）；请记录真实互动逐步推进，确有必要需 force=true 并附说明",
            )
        if forward_steps > 1 and force and not note:
            raise TransitionDenied(status_code=422, detail="跳步推进（force=true）必须附 note 说明真实依据")


# ---------------------------------------------------------------------------
# Interaction 真实性校验
# ---------------------------------------------------------------------------

def validate_interaction_payload(
    *,
    interaction_type: str | None,
    direction: str | None,
    channel: str | None,
    result: str | None,
    revenue: Decimal | None,
    quote_amount: Decimal | None,
    reject_reason: str | None,
) -> dict[str, str]:
    """创建/修改 Interaction 时的反伪造校验，返回规范化字段（type/direction 大写）。"""
    normalized: dict[str, str] = {}
    if interaction_type is not None:
        if interaction_type not in INTERACTION_TYPES:
            raise TransitionDenied(status_code=422, detail=f"interaction_type 必须是 {sorted(INTERACTION_TYPES)} 之一")
        normalized["interaction_type"] = interaction_type
    if direction is not None:
        if direction not in INTERACTION_DIRECTIONS:
            raise TransitionDenied(status_code=422, detail=f"direction 必须是 {sorted(INTERACTION_DIRECTIONS)} 之一")
        normalized["direction"] = direction
    if channel is not None:
        if channel not in INTERACTION_CHANNELS:
            raise TransitionDenied(status_code=422, detail=f"channel 必须是 {sorted(INTERACTION_CHANNELS)} 之一")
        normalized["channel"] = channel

    itype = normalized.get("interaction_type")
    direc = normalized.get("direction")
    if itype and direc:
        allowed = INTERACTION_TYPE_DIRECTIONS.get(itype)
        if allowed and direc not in allowed:
            label = INTERACTION_TYPES[itype]
            raise TransitionDenied(
                status_code=422,
                detail=f"「{label}」的方向只能是 {sorted(allowed)}（客户回复必须 INBOUND，我方触达必须 OUTBOUND，不得伪造方向）",
            )
    if itype == "REPLY" and result is not None and result not in REPLY_CATEGORIES:
        raise TransitionDenied(status_code=422, detail=f"回复分类 result 必须是 {sorted(REPLY_CATEGORIES)} 之一（人工对真实回复分类）")

    if revenue is not None and itype not in REVENUE_ALLOWED_TYPES:
        raise TransitionDenied(status_code=422, detail="只有签约（CONTRACT）/收款（PAYMENT）可以记录收入 revenue；报价金额请记录到 Quote/quote_amount，报价不是收入")
    if quote_amount is not None and itype not in {"QUOTE", "PROPOSAL", "NEGOTIATION"}:
        raise TransitionDenied(status_code=422, detail="quote_amount 只能记录在报价/方案/谈判类型互动中")
    if reject_reason is not None:
        if itype not in REJECT_REASON_ALLOWED_TYPES:
            raise TransitionDenied(status_code=422, detail="拒绝原因只能记录在客户拒绝（REJECTION）互动中；没有真实客户反馈不得编造原因")
        if reject_reason not in EXPERIMENT_REJECT_REASONS:
            raise TransitionDenied(status_code=422, detail=f"reject_reason 必须是 {sorted(EXPERIMENT_REJECT_REASONS)} 之一")
    return normalized


def apply_interaction_side_effects(db: Session, interaction: Interaction) -> None:
    """真实互动写入后的状态联动：Target 状态推进、Opportunity 阶段/意图/联系计数。"""
    itype = interaction.interaction_type
    now = interaction.occurred_at or _now()

    # 1) Target：真实行为推进状态（真实事件驱动允许跨步：互动本身是真实依据；
    #    人工 API 跳步才受状态机保护）
    if interaction.target_id and itype:
        target = db.get(ExperimentTarget, interaction.target_id)
        if target is not None:
            target.last_interaction_at = now
            suggested = INTERACTION_TYPE_TO_TARGET_STATUS.get(itype)
            if suggested:
                try:
                    if suggested == "WON":
                        amount = interaction.revenue
                        transition_target(db, target, "WON", contract_amount=amount,
                                          note=f"来自真实互动 {interaction.id}（{itype}）", force=True)
                    else:
                        transition_target(db, target, suggested,
                                          note=f"来自真实互动 {interaction.id}（{itype}）", force=True)
                except TransitionDenied:
                    pass  # 人工状态已领先/被保护：不回退、不阻塞互动记录
            else:
                target.updated_at = now
            db.flush()

    # 2) Opportunity：阶段推进 + observed_intent + 联系列数（互动未指定机会时继承目标的机会）
    opportunity_id = interaction.opportunity_id
    if not opportunity_id and interaction.target_id:
        target_for_opp = db.get(ExperimentTarget, interaction.target_id)
        opportunity_id = target_for_opp.opportunity_id if target_for_opp else None
    if opportunity_id:
        opportunity = db.get(Opportunity, opportunity_id)
        if opportunity is not None:
            if interaction.direction == "OUTBOUND":
                opportunity.contact_count = (opportunity.contact_count or 0) + 1
                opportunity.last_contacted_at = now
            if itype and itype in INTERACTION_TYPE_TO_OPP_STAGE:
                try:
                    new_stage = INTERACTION_TYPE_TO_OPP_STAGE[itype]
                    validate_opportunity_stage_transition(
                        db, opportunity, new_stage,
                        force=True, note=f"真实互动 {interaction.id}（{itype}）",
                    )
                    if opportunity.stage != new_stage:
                        before = opportunity.stage
                        opportunity.stage = new_stage
                        write_audit(db, "STAGE_CHANGE", "opportunity", opportunity.id, {
                            "stage": new_stage, "before": before, "via": f"interaction:{interaction.id}",
                        })
                except TransitionDenied:
                    pass
            if itype and itype in INTERACTION_TYPE_TO_OBSERVED_INTENT:
                opportunity.observed_intent = INTERACTION_TYPE_TO_OBSERVED_INTENT[itype]
            db.flush()


# ---------------------------------------------------------------------------
# 联系人真实性
# ---------------------------------------------------------------------------

def validate_contact_verification(
    *,
    verification_status: str | None,
    source_record_id: str | None,
    source_url: str | None,
) -> str:
    """联系人验证状态规则：VERIFIED_PUBLIC 必须有真实公开来源（记录或 URL）。"""
    status = verification_status or "UNVERIFIED"
    if status not in CONTACT_VERIFICATION_STATUSES:
        raise TransitionDenied(status_code=422, detail=f"verification_status 必须是 {sorted(CONTACT_VERIFICATION_STATUSES)} 之一")
    if status == "VERIFIED_PUBLIC" and not source_record_id and not source_url:
        raise TransitionDenied(
            status_code=422,
            detail="无来源不能标记 VERIFIED_PUBLIC：公开核实联系人必须提供 source_record_id 或 source_url（禁止生成猜测联系人）",
        )
    return status


def confirm_pain_point(
    db: Session,
    interaction: Interaction,
    pain_point_id: str,
    *,
    note: str | None = None,
    actor: str = "local-user",
) -> PainPoint:
    """PainPoint 真实确认：INFERRED → CONFIRMED 只能由真实客户沟通触发。"""
    pain_point = db.get(PainPoint, pain_point_id)
    if pain_point is None:
        raise TransitionDenied(status_code=404, detail="PainPoint not found")
    if pain_point.company_id != interaction.company_id:
        raise TransitionDenied(status_code=422, detail="PainPoint 与互动不属于同一企业")
    if pain_point.status == "CONFIRMED":
        return pain_point
    if interaction.direction != "INBOUND" and interaction.interaction_type not in {"REPLY", "MEETING", "DEMO"}:
        raise TransitionDenied(status_code=422, detail="痛点确认必须来自真实客户沟通（INBOUND 回复/会议），内部笔记不得升级 CONFIRMED")
    if not (interaction.summary or interaction.response_summary or (note or "")):
        raise TransitionDenied(status_code=422, detail="痛点确认必须附客户原话/依据（summary 或 note）")
    pain_point.status = "CONFIRMED"
    pain_point.confirmed_by_interaction_id = interaction.id
    pain_point.confirmed_at = _now()
    pain_point.confirmed_by = actor
    write_audit(db, "PAIN_CONFIRMED", "pain_point", pain_point.id, {
        "via_interaction": interaction.id, "note": note, "company_id": pain_point.company_id,
    })
    db.flush()
    return pain_point


def confirm_budget(
    db: Session,
    opportunity: Opportunity,
    *,
    budget_text: str,
    interaction_id: str,
    actor: str = "local-user",
) -> Opportunity:
    """预算确认：只有客户明确说出预算才保存；必须引用一条客户来讯（INBOUND）互动作为依据。"""
    text = (budget_text or "").strip()
    if not text:
        raise TransitionDenied(status_code=422, detail="confirmed_budget 需要客户明确说出的预算原文（客户没说就保持 UNKNOWN，禁止猜测）")
    interaction = db.get(Interaction, interaction_id) if interaction_id else None
    if interaction is None:
        raise TransitionDenied(status_code=422, detail="预算确认必须引用一条真实客户来讯（INBOUND）互动作为依据（interaction_id 必填）")
    if interaction.direction != "INBOUND":
        raise TransitionDenied(status_code=422, detail="预算确认必须引用一条客户来讯（INBOUND）互动作为依据")
    opportunity.confirmed_budget = text[:200]
    write_audit(db, "BUDGET_CONFIRMED", "opportunity", opportunity.id, {
        "confirmed_budget": opportunity.confirmed_budget, "via_interaction": interaction_id,
    })
    db.flush()
    return opportunity


# ---------------------------------------------------------------------------
# Quote 状态
# ---------------------------------------------------------------------------

def validate_quote_status(status: str) -> str:
    if status not in QUOTE_STATUSES:
        raise TransitionDenied(status_code=422, detail=f"quote status 必须是 {sorted(QUOTE_STATUSES)} 之一")
    return status
