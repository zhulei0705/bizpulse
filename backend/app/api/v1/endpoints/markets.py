from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.market import Market
from app.schemas.market import MarketCreate, MarketRead
from app.services.audit import write_audit

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets(
    q: str | None = None,
    validation_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Market.market_name.like(like), Market.problem.like(like), Market.target_customer.like(like)))
    if validation_status:
        filters.append(Market.validation_status == validation_status)
    total = db.scalar(select(func.count()).select_from(Market).where(*filters)) or 0
    items = db.scalars(
        select(Market).where(*filters).order_by(Market.market_score.desc().nullslast(), Market.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"success": True, "data": {"items": [MarketRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_market(payload: MarketCreate, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Market).where(Market.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Market slug already exists")
    market = Market(**payload.model_dump())
    db.add(market)
    db.flush()
    write_audit(db, "CREATE", "market", market.id, {"market_name": market.market_name})
    db.commit()
    db.refresh(market)
    return {"success": True, "data": MarketRead.model_validate(market).model_dump(), "message": None}


@router.get("/{market_id}")
def get_market(market_id: str, db: Session = Depends(get_db)) -> dict:
    market = db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"success": True, "data": MarketRead.model_validate(market).model_dump(), "message": None}
