"""T06 互动记录 API：每一次真实商业动作（人工执行；系统不自动外发）。

反伪造规则在 Service 层（validation.validate_interaction_payload）：
- REPLY/REJECTION 必须 INBOUND，OUTREACH/FOLLOW_UP/QUOTE 必须 OUTBOUND；
- revenue 只能记在 CONTRACT/PAYMENT（报价不是收入）；
- reject_reason 只能记在 REJECTION（没有客户真实反馈不得编造原因）。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import INTERACTION_TYPES
from app.db.session import get_db
from app.models.company import Company, CompanyContact
from app.models.experiment import ExperimentTarget, Interaction
from app.models.opportunity import Opportunity
from app.schemas.experiment import ConfirmPainRequest, InteractionCreate, InteractionRead, InteractionUpdate
from app.services.audit import write_audit
from app.services.validation import (
    TransitionDenied,
    apply_interaction_side_effects,
    confirm_pain_point,
    validate_interaction_payload,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])


def serialize_interaction(db: Session, x: Interaction) -> dict:
    data = InteractionRead.model_validate(x).model_dump()
    company = db.get(Company, x.company_id)
    data["company_name"] = company.company_name if company else None
    if x.contact_id:
        contact = db.get(CompanyContact, x.contact_id)
        data["contact_name"] = data["contact_name"] or (contact.name if contact else None)
    return data


def create_interaction_internal(db: Session, data: dict) -> dict:
    """互动创建核心（experiments 兼容端点与全局端点共用）。"""
    if not db.get(Company, data.get("company_id")):
        raise HTTPException(status_code=422, detail="company_id does not exist")
    if data.get("opportunity_id") and not db.get(Opportunity, data["opportunity_id"]):
        raise HTTPException(status_code=422, detail="opportunity_id does not exist")
    if data.get("target_id"):
        target = db.get(ExperimentTarget, data["target_id"])
        if not target:
            raise HTTPException(status_code=422, detail="target_id does not exist")
        data["experiment_id"] = data.get("experiment_id") or target.experiment_id
        data["company_id"] = data.get("company_id") or target.company_id
    if data.get("contact_id") and not db.get(CompanyContact, data["contact_id"]):
        raise HTTPException(status_code=422, detail="contact_id does not exist")

    try:
        normalized = validate_interaction_payload(
            interaction_type=data.get("interaction_type"),
            direction=data.get("direction"),
            channel=data.get("channel"),
            result=data.get("result"),
            revenue=data.get("revenue"),
            quote_amount=data.get("quote_amount"),
            reject_reason=data.get("reject_reason"),
        )
    except TransitionDenied as exc:
        raise exc

    data.update(normalized)
    # direction 缺省时按类型推导（显式校验已通过的情况）
    if not data.get("direction") and data.get("interaction_type"):
        from app.services.validation import INTERACTION_TYPE_DIRECTIONS
        allowed = INTERACTION_TYPE_DIRECTIONS.get(data["interaction_type"])
        if allowed and len(allowed) == 1:
            data["direction"] = next(iter(allowed))
        else:
            data["direction"] = "INTERNAL" if data["interaction_type"] in {"RESEARCH", "NOTE", "CONTRACT", "PILOT"} else "OUTBOUND"
    if not data.get("channel"):
        data["channel"] = "OTHER"

    if data.get("revenue") is not None and not data.get("deal"):
        data["deal"] = True  # 有真实收款/签约金额即真实成交行为

    interaction = Interaction(**data)
    db.add(interaction)
    db.flush()

    try:
        apply_interaction_side_effects(db, interaction)
    except Exception:
        db.rollback()
        raise

    write_audit(db, "CREATE", "interaction", interaction.id, {
        "company_id": interaction.company_id, "experiment_id": interaction.experiment_id,
        "target_id": interaction.target_id, "interaction_type": interaction.interaction_type,
        "direction": interaction.direction, "channel": interaction.channel,
        "has_revenue": interaction.revenue is not None,
        "reject_reason": interaction.reject_reason,
    })
    db.commit()
    db.refresh(interaction)
    return {"success": True, "data": serialize_interaction(db, interaction), "message": None}


@router.get("")
def list_interactions(
    company_id: str | None = None,
    experiment_id: str | None = None,
    target_id: str | None = None,
    opportunity_id: str | None = None,
    interaction_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if company_id:
        filters.append(Interaction.company_id == company_id)
    if experiment_id:
        filters.append(Interaction.experiment_id == experiment_id)
    if target_id:
        filters.append(Interaction.target_id == target_id)
    if opportunity_id:
        filters.append(Interaction.opportunity_id == opportunity_id)
    if interaction_type:
        if interaction_type not in INTERACTION_TYPES:
            raise HTTPException(status_code=422, detail=f"interaction_type 必须是 {sorted(INTERACTION_TYPES)} 之一")
        filters.append(Interaction.interaction_type == interaction_type)
    total = db.scalar(select(func.count()).select_from(Interaction).where(*filters)) or 0
    items = db.scalars(select(Interaction).where(*filters).order_by(Interaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [serialize_interaction(db, x) for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_interaction(payload: InteractionCreate, db: Session = Depends(get_db)) -> dict:
    return create_interaction_internal(db, payload.model_dump())


@router.get("/{interaction_id}")
def get_interaction(interaction_id: str, db: Session = Depends(get_db)) -> dict:
    interaction = db.get(Interaction, interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"success": True, "data": serialize_interaction(db, interaction), "message": None}


@router.patch("/{interaction_id}")
def update_interaction(interaction_id: str, payload: InteractionUpdate, db: Session = Depends(get_db)) -> dict:
    interaction = db.get(Interaction, interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    changes = payload.model_dump(exclude_unset=True)
    try:
        normalized = validate_interaction_payload(
            interaction_type=changes.get("interaction_type", interaction.interaction_type),
            direction=changes.get("direction", interaction.direction),
            channel=changes.get("channel", interaction.channel),
            result=changes.get("result"),
            revenue=changes.get("revenue", interaction.revenue),
            quote_amount=changes.get("quote_amount", interaction.quote_amount),
            reject_reason=changes.get("reject_reason", interaction.reject_reason),
        )
    except TransitionDenied as exc:
        raise exc
    changes.update(normalized)
    before = {k: str(getattr(interaction, k, None)) for k in changes}
    for key, value in changes.items():
        setattr(interaction, key, value)
    db.flush()
    try:
        apply_interaction_side_effects(db, interaction)
    except Exception:
        db.rollback()
        raise
    write_audit(db, "UPDATE", "interaction", interaction.id, {"before": before, "changes": changes})
    db.commit()
    db.refresh(interaction)
    return {"success": True, "data": serialize_interaction(db, interaction), "message": None}


@router.post("/{interaction_id}/confirm-pain")
def confirm_pain(interaction_id: str, payload: ConfirmPainRequest, db: Session = Depends(get_db)) -> dict:
    """PainPoint 真实确认：只能来自真实客户沟通（INBOUND 回复/会议），附客户原话依据。"""
    interaction = db.get(Interaction, interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    try:
        pain_point = confirm_pain_point(db, interaction, payload.pain_point_id, note=payload.note)
    except TransitionDenied as exc:
        db.rollback()
        raise exc
    db.commit()
    return {"success": True, "data": {"id": pain_point.id, "status": pain_point.status, "confirmed_by_interaction_id": pain_point.confirmed_by_interaction_id}, "message": None}
