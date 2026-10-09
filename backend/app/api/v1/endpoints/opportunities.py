from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import LEGACY_STAGE_MAP, OPPORTUNITY_STAGES
from app.db.session import get_db
from app.models.company import Company
from app.models.opportunity import Opportunity, OpportunityEvidence, OpportunityFeedback
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityEvidenceCreate,
    OpportunityRead,
    OpportunityReviewRequest,
    OpportunityStageChangeRequest,
    OpportunityStageUpdate,
)
from app.schemas.experiment import ConfirmBudgetRequest
from app.services.audit import write_audit
from app.services.scoring import OpportunityScoreInput, calculate_opportunity_score

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

VALID_STAGES = set(OPPORTUNITY_STAGES)


def _normalize_stage(stage: str) -> str:
    return LEGACY_STAGE_MAP.get(stage, stage)


def _serialize_with_counts(db: Session, opportunity: Opportunity, company_names: dict[str, str] | None = None) -> dict:
    data = OpportunityRead.model_validate(opportunity).model_dump()
    # T05：JSON 字段在 ORM 中为 *_json 命名，序列化为对外字段名
    data["score_breakdown"] = opportunity.score_breakdown_json or {}
    data["risk_notes"] = opportunity.risk_notes or []
    data["validation_questions"] = opportunity.validation_questions or []
    data["evidence_count"] = (
        db.scalar(select(func.count()).select_from(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opportunity.id)) or 0
    )
    if company_names and opportunity.company_id in company_names:
        data["company_name"] = company_names[opportunity.company_id]
    else:
        data["company_name"] = db.scalar(select(Company.company_name).where(Company.id == opportunity.company_id))
    primary = db.get(Signal, opportunity.primary_signal_id) if opportunity.primary_signal_id else None
    data["trigger_event"] = data.get("trigger_event") or (primary.title if primary else None)
    return data


@router.get("")
def list_opportunities(
    stage: str | None = None,
    grade: str | None = None,
    status: str = "ACTIVE",
    company_id: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if status != "ALL":
        filters.append(Opportunity.status == status)
    if stage:
        filters.append(Opportunity.stage == _normalize_stage(stage))
    if grade:
        filters.append(Opportunity.grade == grade)
    if company_id:
        filters.append(Opportunity.company_id == company_id)
    if min_score is not None:
        filters.append(Opportunity.total_score >= min_score)
    total = db.scalar(select(func.count()).select_from(Opportunity).where(*filters)) or 0
    items = db.scalars(
        select(Opportunity).where(*filters).order_by(Opportunity.total_score.desc(), Opportunity.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    from app.core.constants import VALIDATING_STAGES

    company_names = dict(db.execute(select(Company.id, Company.company_name)).all())
    counts = {
        "pending_review": db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(["NEW", "REVIEW"]), Opportunity.status == "ACTIVE")) or 0,
        "validating": db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(VALIDATING_STAGES), Opportunity.status == "ACTIVE")) or 0,
        "won": db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.stage == "WON")) or 0,
        "rejected": db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.stage == "REJECTED")) or 0,
    }
    return {
        "success": True,
        "data": {
            "items": [_serialize_with_counts(db, x, company_names) for x in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "counts": counts,
        },
        "message": None,
    }


@router.post("")
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=422, detail="company_id does not exist")
    # 证据强制：没有至少 1 条信号证据时禁止生成正式 Opportunity（只能作为待验证线索存在）
    if not payload.primary_signal_id:
        raise HTTPException(
            status_code=422,
            detail="创建正式商业机会必须至少关联 1 条商业信号作为证据（evidence_count=0 时只能保存为待验证线索）",
        )
    primary_signal = db.get(Signal, payload.primary_signal_id)
    if not primary_signal:
        raise HTTPException(status_code=422, detail="primary_signal_id does not exist")
    from app.services.evidence_integrity import signal_issues
    if signal_issues(db,primary_signal):raise HTTPException(status_code=422,detail='INVALID_EVIDENCE：不得由失效证据创建或评分新机会')
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=422, detail=f"Invalid stage, allowed: {', '.join(sorted(VALID_STAGES))}")

    # 来源等级联动：D 级（转载/出处不明）信息不得直接形成高等级商业机会 → 证据分强制 ≤59（触发证据门槛，等级最高 B）
    evidence_score = payload.evidence_score
    signal_record = db.get(SourceRecord, primary_signal.source_record_id)
    if signal_record:
        source = db.get(Source, signal_record.source_id)
        if source and source.reliability_grade == "D":
            evidence_score = min(evidence_score, 59)

    scored = calculate_opportunity_score(OpportunityScoreInput(
        pain=payload.pain_score,
        budget=payload.budget_score,
        intent=payload.intent_score,
        urgency=payload.urgency_score,
        agent_fit=payload.agent_fit_score,
        reachability=payload.reachability_score,
        evidence=evidence_score,
    ), reasons={"evidence": [f"D级来源证据强制降分" if evidence_score < payload.evidence_score else "人工填写证据分"]})
    opportunity = Opportunity(
        **payload.model_dump(exclude={"evidence_score"}),
        evidence_score=evidence_score,
        total_score=scored.score,
        grade=scored.grade,
        score_breakdown_json=scored.breakdown,
        grade_cap_reason=scored.grade_cap_reason,
    )
    db.add(opportunity)
    db.flush()
    # 主信号自动关联为证据，保证机会可追溯
    db.add(OpportunityEvidence(
        opportunity_id=opportunity.id,
        signal_id=primary_signal.id,
        source_record_id=primary_signal.source_record_id,
        evidence_type="SIGNAL",
        evidence_excerpt=primary_signal.title,
    ))
    write_audit(db, "CREATE", "opportunity", opportunity.id, {
        "score": scored.score, "grade": scored.grade, "company_id": opportunity.company_id,
        "primary_signal_id": primary_signal.id, "evidence_score": evidence_score,
    })
    db.commit()
    db.refresh(opportunity)
    return {"success": True, "data": _serialize_with_counts(db, opportunity), "message": None}


@router.get("/{opportunity_id}")
def get_opportunity(opportunity_id: str, db: Session = Depends(get_db)) -> dict:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    data = _serialize_with_counts(db, opportunity)
    evidence_rows = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opportunity_id)).all()
    evidences = []
    for e in evidence_rows:
        record = db.get(SourceRecord, e.source_record_id) if e.source_record_id else None
        signal = db.get(Signal, e.signal_id) if e.signal_id else None
        evidences.append({
            "id": e.id,
            "source_record_id": e.source_record_id,
            "signal_id": e.signal_id,
            "evidence_type": e.evidence_type,
            "evidence_excerpt": e.evidence_excerpt,
            "weight": e.weight,
            "url": record.url if record else None,
            "title": record.title if record else (signal.title if signal else None),
        })
    data["evidences"] = evidences
    return {"success": True, "data": data, "message": None}


@router.post("/{opportunity_id}/review")
def review_opportunity(opportunity_id: str, payload: OpportunityReviewRequest, db: Session = Depends(get_db)) -> dict:
    """人工审核：approve(通过) / reject(驳回) / edit(修改) / ready(加入验证) / need_more_evidence(证据不足)。

    审计记录修改前/修改后；通过（approve/ready）时联动验证其关联证据；
    reject 必须带枚举驳回原因（T05）。
    """
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    now = datetime.now(timezone.utc)
    changes: dict = {}
    before: dict = {"stage": opportunity.stage, "review_status": opportunity.review_status}

    if payload.action in {"approve", "ready"}:
        from app.services.evidence_integrity import opportunity_issues
        issues=opportunity_issues(db, opportunity)
        if issues:raise HTTPException(status_code=422, detail={'code': 'INVALID_EVIDENCE', 'reasons': issues})
        opportunity.stage = "READY"
        opportunity.review_status = "APPROVED"
        _verify_opportunity_evidence(db, opportunity.id, now)
    elif payload.action == "reject":
        # T05：驳回原因（复盘最重要的数据），必须是枚举值
        from app.core.constants import OPPORTUNITY_REJECT_REASONS
        if payload.reject_reason and payload.reject_reason not in OPPORTUNITY_REJECT_REASONS:
            raise HTTPException(status_code=422, detail=f"reject_reason 必须是 {sorted(OPPORTUNITY_REJECT_REASONS)} 之一")
        opportunity.stage = "REJECTED"
        opportunity.review_status = "REJECTED"
        opportunity.reject_reason = payload.reject_reason or "OTHER"
        changes["reject_reason"] = opportunity.reject_reason
    elif payload.action == "need_more_evidence":
        # T05：人工标记证据不足 —— 保持 REVIEW 状态、进入复核清单
        opportunity.review_status = "NEED_MORE_EVIDENCE"
        if opportunity.stage not in {"NEW", "REVIEW"}:
            opportunity.stage = "REVIEW"
    elif payload.action == "edit":
        if not payload.updates:
            raise HTTPException(status_code=422, detail="action=edit 时必须提供 updates 字段")
        updates = payload.updates.model_dump(exclude_unset=True)
        score_fields = {"pain_score", "budget_score", "intent_score", "urgency_score", "agent_fit_score", "reachability_score", "evidence_score"}
        if score_fields & updates.keys():
            from app.services.evidence_integrity import opportunity_issues
            if opportunity_issues(db,opportunity):raise HTTPException(status_code=422,detail='INVALID_EVIDENCE：隔离机会禁止重新评分')
        if updates:
            for key, value in updates.items():
                before[key] = getattr(opportunity, key)
                setattr(opportunity, key, value)
                changes[key] = value
            if score_fields & updates.keys():
                scored = calculate_opportunity_score(OpportunityScoreInput(
                    pain=opportunity.pain_score,
                    budget=opportunity.budget_score,
                    intent=opportunity.intent_score,
                    urgency=opportunity.urgency_score,
                    agent_fit=opportunity.agent_fit_score,
                    reachability=opportunity.reachability_score,
                    evidence=opportunity.evidence_score,
                ))
                before["total_score"] = opportunity.total_score
                before["grade"] = opportunity.grade
                opportunity.total_score = scored.score
                opportunity.grade = scored.grade
                opportunity.score_breakdown_json = scored.breakdown
                opportunity.grade_cap_reason = scored.grade_cap_reason
                changes["total_score"] = scored.score
                changes["grade"] = scored.grade
        opportunity.review_status = "EDITED"

    opportunity.reviewed_at = now
    opportunity.review_note = payload.note
    opportunity.reviewed_by = "local-user"
    after = {"stage": opportunity.stage, "review_status": opportunity.review_status, **changes}
    write_audit(db, "REVIEW", "opportunity", opportunity.id, {
        "action": payload.action, "note": payload.note, "changes": changes,
        "before": before, "after": after,
    })
    db.commit()
    db.refresh(opportunity)
    return {"success": True, "data": _serialize_with_counts(db, opportunity), "message": f"review_{payload.action}_applied"}


def _verify_opportunity_evidence(db: Session, opportunity_id: str, verified_at: datetime) -> None:
    """人工审核通过 = 关联证据被人工确认过：更新验证状态与验证时间（不删除任何历史记录）。"""
    evidence_rows = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opportunity_id)).all()
    for e in evidence_rows:
        if e.source_record_id:
            record = db.get(SourceRecord, e.source_record_id)
            if record:
                record.verification_status = "VERIFIED"
                record.last_verified_at = verified_at
        if e.signal_id:
            signal = db.get(Signal, e.signal_id)
            if signal:
                signal.verification_status = "VERIFIED"


@router.patch("/{opportunity_id}/stage")
def update_stage(opportunity_id: str, payload: OpportunityStageChangeRequest, db: Session = Depends(get_db)) -> dict:
    """机会验证阶段流转（T06 状态机保护：未审核不得进入验证、禁止大跨度跳跃、WON 需真实合同金额）。"""
    from app.services.validation import TransitionDenied, validate_opportunity_stage_transition

    stage = _normalize_stage(payload.stage)
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    try:
        validate_opportunity_stage_transition(
            db, opportunity, stage,
            reject_reason=payload.reject_reason,
            contract_amount=payload.contract_amount,
            force=payload.force,
            note=payload.note,
        )
    except TransitionDenied as exc:
        db.rollback()
        raise exc
    before = opportunity.stage
    opportunity.stage = stage
    if payload.reject_reason and stage == "REJECTED":
        opportunity.reject_reason = payload.reject_reason
    if payload.owner is not None:
        opportunity.owner = payload.owner
    write_audit(db, "STAGE_CHANGE", "opportunity", opportunity.id, {
        "before": before, "stage": stage, "owner": payload.owner,
        "reject_reason": payload.reject_reason, "force": payload.force, "note": payload.note,
    })
    db.commit()
    db.refresh(opportunity)
    return {"success": True, "data": _serialize_with_counts(db, opportunity), "message": None}


@router.post("/{opportunity_id}/add-to-experiment")
def add_to_experiment(opportunity_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
    """机会加入实验（任务书五十四）：必须人工审核通过（READY 及之后）。"""
    from app.models.experiment import Experiment, ExperimentOpportunity, ExperimentTarget
    experiment_id = (payload or {}).get("experiment_id")
    if not experiment_id:
        raise HTTPException(status_code=422, detail="experiment_id is required")
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if opportunity.review_status != "APPROVED":
        raise HTTPException(status_code=422, detail="机会尚未人工审核通过（review_status != APPROVED），不能加入实验")
    if opportunity.stage not in {"READY", "CONTACTED", "REPLIED", "MEETING", "QUOTED", "PILOT"}:
        raise HTTPException(status_code=422, detail="机会需处于 READY（已审核待验证）或之后阶段")

    duplicate = db.scalar(select(ExperimentOpportunity).where(
        ExperimentOpportunity.experiment_id == experiment_id,
        ExperimentOpportunity.opportunity_id == opportunity_id,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="该机会已在此实验中")
    db.add(ExperimentOpportunity(experiment_id=experiment_id, opportunity_id=opportunity_id))
    target = db.scalar(select(ExperimentTarget).where(
        ExperimentTarget.experiment_id == experiment_id,
        ExperimentTarget.company_id == opportunity.company_id,
    ))
    created_target = False
    if target is None:
        target = ExperimentTarget(
            experiment_id=experiment_id,
            company_id=opportunity.company_id,
            opportunity_id=opportunity_id,
            added_at=datetime.now(timezone.utc),
        )
        db.add(target)
        experiment.target_company_count = (experiment.target_company_count or 0) + 1
        created_target = True
    else:
        target.opportunity_id = target.opportunity_id or opportunity_id
    db.flush()
    write_audit(db, "ADD_TO_EXPERIMENT", "experiment_target", target.id, {
        "experiment_id": experiment_id, "opportunity_id": opportunity_id,
        "company_id": opportunity.company_id, "target_created": created_target,
    })
    db.commit()
    return {
        "success": True,
        "data": {"experiment_id": experiment_id, "opportunity_id": opportunity_id, "target_id": target.id, "target_created": created_target},
        "message": None,
    }


@router.get("/{opportunity_id}/feedback")
def get_opportunity_feedback(opportunity_id: str, db: Session = Depends(get_db)) -> dict:
    """预测 vs 真实结果反馈（T06 只积累数据用于校准分析，不自动训练模型）。"""
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    rows = db.scalars(select(OpportunityFeedback).where(OpportunityFeedback.opportunity_id == opportunity_id).order_by(OpportunityFeedback.feedback_at.desc())).all()
    data = [{
        "id": f.id, "target_id": f.target_id,
        "predicted_score": f.predicted_score, "predicted_grade": f.predicted_grade,
        "actual_reply": f.actual_reply, "actual_meeting": f.actual_meeting,
        "actual_quote": f.actual_quote, "actual_pilot": f.actual_pilot,
        "actual_win": f.actual_win, "actual_revenue": f.actual_revenue,
        "reject_reason": f.reject_reason, "notes": f.notes,
        "feedback_at": f.feedback_at.isoformat() if f.feedback_at else None,
    } for f in rows]
    return {"success": True, "data": data, "message": None}


@router.post("/{opportunity_id}/confirm-budget")
def confirm_opportunity_budget(opportunity_id: str, payload: ConfirmBudgetRequest, db: Session = Depends(get_db)) -> dict:
    """预算确认：客户明确说出的预算原文；必须引用一条 INBOUND 互动作为依据。"""
    from app.services.validation import TransitionDenied, confirm_budget

    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    try:
        opportunity = confirm_budget(db, opportunity, budget_text=payload.budget_text, interaction_id=payload.interaction_id)
    except TransitionDenied as exc:
        db.rollback()
        raise exc
    db.commit()
    return {"success": True, "data": {"id": opportunity.id, "confirmed_budget": opportunity.confirmed_budget}, "message": None}


@router.post("/{opportunity_id}/evidences")
def add_evidence(opportunity_id: str, payload: OpportunityEvidenceCreate, db: Session = Depends(get_db)) -> dict:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if not payload.source_record_id and not payload.signal_id:
        raise HTTPException(status_code=422, detail="At least one evidence source is required")
    if payload.source_record_id and not db.get(SourceRecord, payload.source_record_id):
        raise HTTPException(status_code=422, detail="source_record_id does not exist")
    if payload.signal_id and not db.get(Signal, payload.signal_id):
        raise HTTPException(status_code=422, detail="signal_id does not exist")
    evidence = OpportunityEvidence(opportunity_id=opportunity_id, **payload.model_dump())
    db.add(evidence)
    db.flush()
    write_audit(db, "ADD_EVIDENCE", "opportunity", opportunity.id, {"evidence_id": evidence.id})
    db.commit()
    return {"success": True, "data": {"id": evidence.id}, "message": None}
