from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.experiment import Experiment, ExperimentOpportunity, ExperimentTarget, Interaction
from app.models.market import Market
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentRead,
    ExperimentTargetCreate,
    ExperimentTargetRead,
    ExperimentTargetUpdate,
    ExperimentUpdate,
    InteractionCreate,
)
from app.core.constants import EXPERIMENT_CONCLUSIONS, EXPERIMENT_STATUSES
from app.services.audit import write_audit
from app.services.metrics import experiment_funnel, experiment_metrics, interaction_metrics
from app.services.validation import TransitionDenied, transition_target

router = APIRouter(prefix="/experiments", tags=["experiments"])
target_router = APIRouter(prefix="/experiment-targets", tags=["experiments"])


def _serialize_experiment(exp: Experiment) -> dict:
    return ExperimentRead.model_validate(exp).model_dump()


@router.get("")
def list_experiments(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = [Experiment.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(Experiment).where(*filters)) or 0
    items = db.scalars(select(Experiment).where(*filters).order_by(Experiment.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = {
        key: db.scalar(select(func.count()).select_from(Experiment).where(Experiment.status == key)) or 0
        for key in EXPERIMENT_STATUSES
    }
    return {
        "success": True,
        "data": {"items": [_serialize_experiment(x) for x in items], "total": total, "page": page, "page_size": page_size, "counts": counts},
        "message": None,
    }


@router.post("")
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)) -> dict:
    if payload.status not in EXPERIMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status 必须是 {sorted(EXPERIMENT_STATUSES)} 之一")
    if payload.market_id and not db.get(Market, payload.market_id):
        raise HTTPException(status_code=422, detail="market_id does not exist")
    exp = Experiment(**payload.model_dump())
    db.add(exp)
    db.flush()
    write_audit(db, "CREATE", "experiment", exp.id, {"name": exp.name, "hypothesis": (exp.hypothesis or "")[:200]})
    db.commit()
    db.refresh(exp)
    return {"success": True, "data": _serialize_experiment(exp), "message": None}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    data = _serialize_experiment(exp)
    data["metrics"] = experiment_metrics(db, experiment_id)
    data["interaction_stats"] = interaction_metrics(db, experiment_id)
    data["funnel"] = experiment_funnel(db, experiment_id)
    return {"success": True, "data": data, "message": None}


@router.patch("/{experiment_id}")
def update_experiment(experiment_id: str, payload: ExperimentUpdate, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in EXPERIMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status 必须是 {sorted(EXPERIMENT_STATUSES)} 之一")
    if "conclusion" in changes and changes["conclusion"] and changes["conclusion"] not in EXPERIMENT_CONCLUSIONS:
        raise HTTPException(status_code=422, detail=f"conclusion 必须是 {sorted(EXPERIMENT_CONCLUSIONS)} 之一")
    before = {k: getattr(exp, k) for k in changes}
    for key, value in changes.items():
        setattr(exp, key, value)
    write_audit(db, "UPDATE", "experiment", exp.id, {"before": {k: str(v) for k, v in before.items()}, "changes": changes})
    db.commit()
    db.refresh(exp)
    return {"success": True, "data": _serialize_experiment(exp), "message": None}


@router.post("/{experiment_id}/start")
def start_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status not in {"DRAFT", "READY", "PAUSED"}:
        raise HTTPException(status_code=422, detail=f"当前状态 {exp.status} 不能开始实验")
    before = exp.status
    exp.status = "RUNNING"
    exp.started_at = exp.started_at or datetime.now(timezone.utc)
    # T08.0 P1-1：启动前一致性校验（不修改数据，只输出质量警告）
    from app.services.experiment_validation import validate_experiment_consistency

    warnings = validate_experiment_consistency(exp)
    # T07 Experiment Snapshot：冻结假设/模型版本/报价假设/目标筛选规则，保证结果可解释
    from app.core.config import settings
    from app.analyzers import prompts
    exp.snapshot_json = {
        "snapshotted_at": datetime.now(timezone.utc).isoformat(),
        "market_hypothesis": exp.hypothesis,
        "target_customer": exp.target_customer,
        "value_proposition": exp.value_proposition,
        "offer": {
            "offer_name": exp.offer_name,
            "offer_description": exp.offer_description,
            "price_amount": float(exp.price_amount) if exp.price_amount is not None else None,
            "price_currency": exp.price_currency,
            "price_type": exp.price_type,
            "pricing_hypothesis": exp.pricing_hypothesis,
        },
        "success_criteria": exp.success_criteria,
        "failure_criteria": exp.failure_criteria,
        "score_model_version": "SCORE_ENGINE_V1_T05",
        "prompt_version": prompts.OPPORTUNITY_GENERATOR_V1,
        "target_selection_rule": "已审核机会 + 真实证据 + 30天信号优先；人工复核后加入",
        "llm_configured": bool(settings.llm_api_key),
        "targets_at_start": exp.target_company_count,
        "consistency_warnings": warnings,
    }
    write_audit(db, "EXPERIMENT_STARTED", "experiment", exp.id, {
        "before": before, "after": "RUNNING", "snapshot": True, "consistency_warnings": warnings,
    })
    db.commit()
    db.refresh(exp)
    data = _serialize_experiment(exp)
    data["consistency_warnings"] = warnings
    return {"success": True, "data": data, "message": None}


@router.post("/{experiment_id}/complete")
def complete_experiment(experiment_id: str, payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status == "COMPLETED":
        raise HTTPException(status_code=409, detail="实验已完成")
    conclusion = (payload or {}).get("conclusion")
    if conclusion and conclusion not in EXPERIMENT_CONCLUSIONS:
        raise HTTPException(status_code=422, detail=f"conclusion 必须是 {sorted(EXPERIMENT_CONCLUSIONS)} 之一（V1 由人工判断，AI 只能建议）")
    before = {"status": exp.status, "conclusion": exp.conclusion}
    exp.status = "COMPLETED"
    exp.ended_at = datetime.now(timezone.utc)
    if conclusion:
        exp.conclusion = conclusion
    exp.conclusion_notes = (payload or {}).get("notes") or exp.conclusion_notes
    write_audit(db, "EXPERIMENT_COMPLETED", "experiment", exp.id, {
        "before": before, "after": {"status": "COMPLETED", "conclusion": exp.conclusion},
        "metrics": experiment_metrics(db, experiment_id),
    })
    db.commit()
    db.refresh(exp)
    return {"success": True, "data": _serialize_experiment(exp), "message": None}


# ---------------------------------------------------------------------------
# 验证目标企业（ValidationTarget）
# ---------------------------------------------------------------------------

def _serialize_target(db: Session, target: ExperimentTarget) -> dict:
    data = ExperimentTargetRead.model_validate(target).model_dump()
    company = db.get(Company, target.company_id)
    data["company_name"] = company.company_name if company else None
    if target.opportunity_id:
        opp = db.get(Opportunity, target.opportunity_id)
        if opp:
            data["opportunity_title"] = opp.title
            data["opportunity_score"] = opp.total_score
            data["opportunity_grade"] = opp.grade
    return data


@router.get("/{experiment_id}/targets")
def list_targets(experiment_id: str, status: str | None = None, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    filters = [ExperimentTarget.experiment_id == experiment_id]
    if status:
        filters.append(ExperimentTarget.status == status)
    items = db.scalars(select(ExperimentTarget).where(*filters).order_by(ExperimentTarget.priority.asc(), ExperimentTarget.updated_at.desc())).all()
    return {"success": True, "data": [_serialize_target(db, x) for x in items], "message": None}


@router.post("/{experiment_id}/targets")
def add_target(experiment_id: str, payload: ExperimentTargetCreate, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(status_code=422, detail="company_id does not exist")
    if payload.opportunity_id:
        opportunity = db.get(Opportunity, payload.opportunity_id)
        if not opportunity:
            raise HTTPException(status_code=422, detail="opportunity_id does not exist")
        from app.services.evidence_integrity import opportunity_issues
        if opportunity_issues(db,opportunity):raise HTTPException(status_code=422,detail='INVALID_EVIDENCE：隔离机会不能加入实验')
        if opportunity.review_status != "APPROVED":
            # 任务书七十五：未审核机会禁止直接加入正式 Experiment
            raise HTTPException(status_code=422, detail="机会尚未人工审核通过（review_status != APPROVED），不能加入正式实验")
        if opportunity.stage not in {"READY", "CONTACTED", "REPLIED", "MEETING", "QUOTED", "PILOT"}:
            raise HTTPException(status_code=422, detail="机会需处于 READY（已审核待验证）或之后的阶段才能加入实验")
        duplicate = db.scalar(select(ExperimentOpportunity).where(
            ExperimentOpportunity.experiment_id == experiment_id, ExperimentOpportunity.opportunity_id == payload.opportunity_id))
        if duplicate is None:
            db.add(ExperimentOpportunity(experiment_id=experiment_id, opportunity_id=payload.opportunity_id))
    existing = db.scalar(select(ExperimentTarget).where(
        ExperimentTarget.experiment_id == experiment_id, ExperimentTarget.company_id == payload.company_id))
    if existing:
        raise HTTPException(status_code=409, detail="该企业已在本实验的目标列表中")
    target = ExperimentTarget(
        experiment_id=experiment_id,
        company_id=payload.company_id,
        opportunity_id=payload.opportunity_id,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
        added_at=datetime.now(timezone.utc),
        status="NEW",
        reached_stage="NEW",
    )
    db.add(target)
    exp.target_company_count = (exp.target_company_count or 0) + 1
    db.flush()
    write_audit(db, "ADD_TO_EXPERIMENT", "experiment_target", target.id, {
        "experiment_id": experiment_id, "company_id": payload.company_id,
        "opportunity_id": payload.opportunity_id, "company_name": company.company_name,
    })
    db.commit()
    db.refresh(target)
    return {"success": True, "data": _serialize_target(db, target), "message": None}


@target_router.patch("/{target_id}")
def update_target(target_id: str, payload: ExperimentTargetUpdate, db: Session = Depends(get_db)) -> dict:
    target = db.get(ExperimentTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.pop("status", None)
    reject_reason = changes.pop("reject_reason", None)
    contract_amount = changes.pop("contract_amount", None)
    force = changes.pop("force", False)
    note = changes.pop("notes", None)
    if new_status:
        try:
            transition_target(
                db, target, new_status,
                note=note, reject_reason=reject_reason, contract_amount=contract_amount,
                next_action=changes.get("next_action"), next_action_at=changes.get("next_action_at"),
                force=force,
            )
        except TransitionDenied as exc:
            db.rollback()
            raise exc
    else:
        for key, value in changes.items():
            setattr(target, key, value)
        db.flush()
    db.commit()
    db.refresh(target)
    return {"success": True, "data": _serialize_target(db, target), "message": None}


@router.get("/{experiment_id}/funnel")
def get_funnel(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Experiment, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"success": True, "data": experiment_funnel(db, experiment_id), "message": None}


# ---------------------------------------------------------------------------
# T07：目标选择（可解释）/ Validation Brief / 报告 / 导出
# ---------------------------------------------------------------------------

def _compute_selection_reason(db: Session, opportunity: Opportunity | None, company_id: str) -> list[str]:
    """选择理由（任务书五十九）：枚举 + 具体数值，不能只写"AI推荐"。"""
    from datetime import timedelta

    from app.models.company import CompanyContact
    from app.models.signal import Signal

    reasons: list[str] = []
    if opportunity is not None:
        if opportunity.total_score >= 75:
            reasons.append(f"HIGH_SCORE(总分{opportunity.total_score})")
        if opportunity.intent_score >= 75:
            reasons.append(f"HIGH_INTENT(意图分{opportunity.intent_score})")
        if opportunity.evidence_score >= 75:
            reasons.append(f"HIGH_EVIDENCE(证据分{opportunity.evidence_score})")
        if opportunity.urgency_score >= 75:
            reasons.append(f"HIGH_URGENCY(紧急度{opportunity.urgency_score})")
        latest = db.scalar(select(Signal).where(
            Signal.company_id == company_id, Signal.status == "APPROVED",
        ).order_by(Signal.collected_at.desc()).limit(1))
        if latest and latest.collected_at:
            collected = latest.collected_at if latest.collected_at.tzinfo else latest.collected_at.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - collected).days
            if days <= 30:
                reasons.append(f"FRESH_SIGNAL(最新信号{days}天前)")
    contacts = db.scalars(select(CompanyContact).where(
        CompanyContact.company_id == company_id,
        CompanyContact.verification_status.in_(["VERIFIED_PUBLIC", "USER_PROVIDED"]),
    )).all()
    if contacts:
        reasons.append(f"REACHABLE({len(contacts)}个可用联系人)")
    if not reasons:
        reasons.append("MANUAL_PICK(人工指定)")
    return reasons


@router.post("/{experiment_id}/targets/select")
def select_targets(experiment_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
    """T07 从已审核机会批量选择验证目标（每家记录 selection_reason，选择必须可解释）。

    body: {"opportunity_ids": [...]} 或 {"company_ids": [...]}；max_count 默认 30。
    基础条件（任务书十四）：机会已人工审核、有证据、公司真实存在。
    """
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    opportunity_ids: list[str] = list((payload or {}).get("opportunity_ids") or [])
    company_ids: list[str] = list((payload or {}).get("company_ids") or [])
    max_count = int((payload or {}).get("max_count") or 30)

    selected: list[dict] = []
    skipped: list[dict] = []

    def _try_add(company_id: str, opportunity_id: str | None, existing_opp: Opportunity | None) -> None:
        if len(selected) >= max_count:
            return
        company = db.get(Company, company_id)
        if company is None:
            skipped.append({"company_id": company_id, "reason": "company_not_found"})
            return
        existing = db.scalar(select(ExperimentTarget).where(
            ExperimentTarget.experiment_id == experiment_id,
            ExperimentTarget.company_id == company_id,
        ))
        if existing is not None:
            skipped.append({"company_id": company_id, "reason": "already_in_experiment"})
            return
        if existing_opp is not None:
            from app.services.evidence_integrity import opportunity_issues
            if opportunity_issues(db,existing_opp):
                skipped.append({'company_id':company_id,'reason':'INVALID_EVIDENCE'})
                return
            if existing_opp.review_status != "APPROVED":
                skipped.append({"company_id": company_id, "reason": "opportunity_not_approved"})
                return
            if not db.scalar(select(OpportunityEvidence.id).where(OpportunityEvidence.opportunity_id == existing_opp.id).limit(1)):
                skipped.append({"company_id": company_id, "reason": "no_evidence"})
                return
        target = ExperimentTarget(
            experiment_id=experiment_id,
            company_id=company_id,
            opportunity_id=opportunity_id,
            added_at=datetime.now(timezone.utc),
            status="NEW",
            reached_stage="NEW",
            selection_reason=_compute_selection_reason(db, existing_opp, company_id),
        )
        db.add(target)
        exp.target_company_count = (exp.target_company_count or 0) + 1
        db.flush()
        selected.append({
            "target_id": target.id, "company_id": company_id,
            "company_name": company.company_name, "opportunity_id": opportunity_id,
            "selection_reason": target.selection_reason,
        })
        write_audit(db, "ADD_TO_EXPERIMENT", "experiment_target", target.id, {
            "experiment_id": experiment_id, "company_id": company_id,
            "opportunity_id": opportunity_id, "selection_reason": target.selection_reason,
            "via": "targets/select",
        })

    if opportunity_ids:
        for oid in opportunity_ids:
            opp = db.get(Opportunity, oid)
            if opp is None:
                skipped.append({"opportunity_id": oid, "reason": "opportunity_not_found"})
                continue
            _try_add(opp.company_id, opp.id, opp)
    for cid in company_ids:
        opp = db.scalar(select(Opportunity).where(
            Opportunity.company_id == cid, Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE",
        ).order_by(Opportunity.total_score.desc()).limit(1))
        _try_add(cid, opp.id if opp else None, opp)

    db.commit()
    return {
        "success": True,
        "data": {"selected": selected, "selected_count": len(selected), "skipped": skipped},
        "message": None,
    }


@target_router.get("/{target_id}/brief")
def get_target_brief(target_id: str, db: Session = Depends(get_db)) -> dict:
    """T07 Validation Brief / Outreach Package（任务书三十一）：只读聚合，不自动发送。"""
    from app.services.brief import build_validation_brief

    target = db.get(ExperimentTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"success": True, "data": build_validation_brief(db, target), "message": None}


@router.get("/{experiment_id}/report")
def get_experiment_report(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    """T07 实验报告：【真实结果】来自数据库 +【系统分析】只读统计描述。"""
    from app.services.brief import build_experiment_report

    if not db.get(Experiment, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"success": True, "data": build_experiment_report(db, experiment_id), "message": None}


@router.get("/{experiment_id}/export.csv")
def export_experiment_csv(experiment_id: str, db: Session = Depends(get_db)) -> Response:
    """T07 数据导出（任务书五十七）：目标企业明细 CSV。"""
    from app.services.brief import export_targets_csv

    if not db.get(Experiment, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    buffer = export_targets_csv(db, experiment_id)
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=experiment_{experiment_id}_targets.csv"},
    )


@router.get("/{experiment_id}/metrics")
def get_metrics(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Experiment, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    data = experiment_metrics(db, experiment_id)
    data["interaction_stats"] = interaction_metrics(db, experiment_id)
    return {"success": True, "data": data, "message": None}


@router.get("/{experiment_id}/interactions")
def list_experiment_interactions(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Experiment, experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    items = db.scalars(select(Interaction).where(Interaction.experiment_id == experiment_id).order_by(Interaction.created_at.desc())).all()
    from app.api.v1.endpoints.interactions import serialize_interaction
    return {"success": True, "data": [serialize_interaction(db, x) for x in items], "message": None}


@router.post("/{experiment_id}/interactions")
def add_interaction(experiment_id: str, payload: InteractionCreate, db: Session = Depends(get_db)) -> dict:
    """兼容旧端点：实验下记录互动（内部走全局互动服务，保持联动与审计一致）。"""
    from app.api.v1.endpoints.interactions import create_interaction_internal
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    data = payload.model_dump()
    data["experiment_id"] = experiment_id
    return create_interaction_internal(db, data)
