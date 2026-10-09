"""T06 报价 API：真实报价记录。

报价金额永远不是收入（revenue 只能来自 CONTRACT/PAYMENT 互动与真实成交 Outcome）；
VIEWED 状态只有在真实获知（客户确认查看）时才能记录，不假设。
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.experiment import ExperimentTarget, Quote
from app.models.opportunity import Opportunity
from app.schemas.experiment import QuoteCreate, QuoteRead, QuoteUpdate
from app.services.audit import write_audit
from app.services.validation import TransitionDenied, validate_quote_status

router = APIRouter(prefix="/quotes", tags=["quotes"])


def serialize_quote(db: Session, q: Quote) -> dict:
    data = QuoteRead.model_validate(q).model_dump()
    company = db.get(Company, q.company_id)
    data["company_name"] = company.company_name if company else None
    return data


@router.get("")
def list_quotes(
    company_id: str | None = None,
    experiment_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if company_id:
        filters.append(Quote.company_id == company_id)
    if experiment_id:
        filters.append(Quote.experiment_id == experiment_id)
    if status:
        filters.append(Quote.status == status)
    total = db.scalar(select(func.count()).select_from(Quote).where(*filters)) or 0
    items = db.scalars(select(Quote).where(*filters).order_by(Quote.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [serialize_quote(db, x) for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_quote(payload: QuoteCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=422, detail="company_id does not exist")
    if payload.opportunity_id and not db.get(Opportunity, payload.opportunity_id):
        raise HTTPException(status_code=422, detail="opportunity_id does not exist")
    if payload.target_id and not db.get(ExperimentTarget, payload.target_id):
        raise HTTPException(status_code=422, detail="target_id does not exist")
    try:
        status = validate_quote_status(payload.status)
    except TransitionDenied as exc:
        raise exc
    if status == "VIEWED" and payload.sent_at is None:
        # VIEWED 只有真实获知才能记录：还没有发送过的报价不能"已被查看"
        raise HTTPException(status_code=422, detail="报价尚未发送（sent_at 为空），不能记录 VIEWED 状态（不假设客户已查看）")
    data = payload.model_dump()
    data["status"] = status
    quote = Quote(**data)
    if quote.status in {"SENT", "VIEWED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"} and quote.sent_at is None:
        quote.sent_at = datetime.now(timezone.utc)
    db.add(quote)
    db.flush()

    # 报价联动：目标企业进入 QUOTED、机会阶段推进（真实动作驱动，内部放行跨步）
    if quote.target_id:
        from app.services.validation import transition_target
        target = db.get(ExperimentTarget, quote.target_id)
        if target:
            try:
                transition_target(db, target, "QUOTED", force=True,
                                  note=f"真实报价 {quote.id}（{quote.amount} {quote.currency}）")
            except TransitionDenied:
                pass
    if quote.opportunity_id:
        opportunity = db.get(Opportunity, quote.opportunity_id)
        if opportunity and opportunity.stage in {"CONTACTED", "REPLIED", "MEETING", "QUOTED"}:
            opportunity.observed_intent = opportunity.observed_intent or "QUOTE_REQUESTED"

    write_audit(db, "CREATE", "quote", quote.id, {
        "company_id": quote.company_id, "amount": float(quote.amount), "currency": quote.currency,
        "status": quote.status, "experiment_id": quote.experiment_id,
    })
    db.commit()
    db.refresh(quote)
    return {"success": True, "data": serialize_quote(db, quote), "message": None}


@router.get("/{quote_id}")
def get_quote(quote_id: str, db: Session = Depends(get_db)) -> dict:
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"success": True, "data": serialize_quote(db, quote), "message": None}


@router.patch("/{quote_id}")
def update_quote(quote_id: str, payload: QuoteUpdate, db: Session = Depends(get_db)) -> dict:
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"]:
        try:
            changes["status"] = validate_quote_status(changes["status"])
        except TransitionDenied as exc:
            raise exc
        new_status = changes["status"]
        if new_status == "VIEWED" and quote.sent_at is None and changes.get("sent_at") is None:
            raise HTTPException(status_code=422, detail="报价尚未发送，不能记录 VIEWED 状态（不假设客户已查看）")
        if new_status in {"SENT", "VIEWED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"} and quote.sent_at is None and changes.get("sent_at") is None:
            changes["sent_at"] = datetime.now(timezone.utc)
    before = {k: str(getattr(quote, k, None)) for k in changes}
    for key, value in changes.items():
        setattr(quote, key, value)
    write_audit(db, "UPDATE", "quote", quote.id, {"before": before, "changes": changes})
    db.commit()
    db.refresh(quote)
    return {"success": True, "data": serialize_quote(db, quote), "message": None}
