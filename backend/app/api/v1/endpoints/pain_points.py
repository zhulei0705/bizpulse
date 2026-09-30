from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.pain_point import PainPoint
from app.schemas.pain_point import PainPointCreate, PainPointRead
from app.services.audit import write_audit

router = APIRouter(prefix="/pain-points", tags=["pain-points"])


@router.get("")
def list_pain_points(
    company_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if company_id:
        filters.append(PainPoint.company_id == company_id)
    if status:
        filters.append(PainPoint.status == status)
    total = db.scalar(select(func.count()).select_from(PainPoint).where(*filters)) or 0
    items = db.scalars(select(PainPoint).where(*filters).order_by(PainPoint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [PainPointRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_pain_point(payload: PainPointCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=422, detail="company_id does not exist")
    point = PainPoint(**payload.model_dump())
    db.add(point)
    db.flush()
    write_audit(db, "CREATE", "pain_point", point.id, {"category": point.category})
    db.commit()
    db.refresh(point)
    return {"success": True, "data": PainPointRead.model_validate(point).model_dump(), "message": None}
