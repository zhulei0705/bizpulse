from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.models.pain_point import PainPoint
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.opportunity import OpportunityRead
from app.schemas.pain_point import PainPointRead
from app.schemas.signal import SignalRead
from app.schemas.source import SourceRecordRead
from app.services.audit import write_audit

router = APIRouter(prefix="/companies", tags=["companies"])

_SORTABLE = {
    "updated_at": Company.updated_at.desc(),
    "created_at": Company.created_at.desc(),
    "company_name": Company.company_name.asc(),
    "pulse_score": Company.pulse_score.desc().nullslast(),
}


def _normalize_name(name: str) -> str:
    return "".join(name.lower().split())


@router.get("")
def list_companies(
    q: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    province: str | None = None,
    city: str | None = None,
    opportunity_level: str | None = None,
    sort: str = Query(default="updated_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Company.company_name.like(like), Company.normalized_name.like(like), Company.domain.like(like)))
    if industry:
        filters.append(Company.industry == industry)
    if country:
        filters.append(Company.country == country)
    if province:
        filters.append(Company.province == province)
    if city:
        filters.append(Company.city == city)
    if opportunity_level:
        filters.append(Company.opportunity_level == opportunity_level)

    order = _SORTABLE.get(sort, Company.updated_at.desc())
    total = db.scalar(select(func.count()).select_from(Company).where(*filters)) or 0
    items = db.scalars(
        select(Company).where(*filters).order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()

    from app.services.dashboard import start_of_utc_day

    today_new = db.scalar(select(func.count()).select_from(Company).where(Company.created_at >= start_of_utc_day())) or 0
    stats = {
        "total_companies": total,
        "today_new": today_new,
    }
    return {
        "success": True,
        "data": {"items": [CompanyRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size, "stats": stats},
        "message": None,
    }


@router.post("")
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)) -> dict:
    normalized = payload.normalized_name or _normalize_name(payload.company_name)
    duplicate = db.scalar(select(Company).where(Company.normalized_name == normalized))
    if duplicate:
        raise HTTPException(status_code=409, detail="Company with the same normalized name already exists")
    company = Company(**payload.model_dump(exclude={"normalized_name"}), normalized_name=normalized)
    db.add(company)
    db.flush()
    write_audit(db, "CREATE", "company", company.id, {"company_name": company.company_name})
    db.commit()
    db.refresh(company)
    return {"success": True, "data": CompanyRead.model_validate(company).model_dump(), "message": None}


def _signal_with_evidence(db: Session, signal: Signal) -> dict:
    data = SignalRead.model_validate(signal).model_dump()
    record = db.get(SourceRecord, signal.source_record_id)
    source = db.get(Source, record.source_id) if record else None
    data["evidence"] = None if not record else {
        "source_record_id": record.id,
        "url": record.url,
        "title": record.title,
        "published_at": record.published_at,
        "collected_at": record.collected_at,
        "excerpt": (record.raw_text or "")[:400] or None,
        "source_name": source.name if source else None,
        "reliability_grade": source.reliability_grade if source else None,
        "reliability_score": source.reliability_score if source else None,
        "verification_status": record.verification_status,
        "last_verified_at": record.last_verified_at,
    }
    company_name = db.scalar(select(Company.company_name).where(Company.id == signal.company_id)) if signal.company_id else None
    data["company_name"] = company_name
    return data


@router.get("/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    signal_count = db.scalar(select(func.count()).select_from(Signal).where(Signal.company_id == company_id)) or 0
    opportunity_count = db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.company_id == company_id)) or 0
    data = CompanyRead.model_validate(company).model_dump()
    data.update({"signal_count": signal_count, "opportunity_count": opportunity_count})
    return {"success": True, "data": data, "message": None}


@router.get("/{company_id}/overview")
def get_company_overview(company_id: str, db: Session = Depends(get_db)) -> dict:
    """企业详情页聚合：基础信息 + 商业信号 + AI推断痛点 + 机会 + 原始证据。"""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    signals = db.scalars(select(Signal).where(Signal.company_id == company_id).order_by(Signal.collected_at.desc()).limit(100)).all()
    pain_points = db.scalars(select(PainPoint).where(PainPoint.company_id == company_id).order_by(PainPoint.updated_at.desc()).limit(50)).all()
    opportunities = db.scalars(
        select(Opportunity).where(Opportunity.company_id == company_id, Opportunity.status == "ACTIVE").order_by(Opportunity.total_score.desc())
    ).all()
    records = db.scalars(select(SourceRecord).where(SourceRecord.company_id == company_id).order_by(SourceRecord.collected_at.desc()).limit(100)).all()

    evidence_counts = dict(db.execute(
        select(OpportunityEvidence.opportunity_id, func.count()).group_by(OpportunityEvidence.opportunity_id)
    ).all())

    return {
        "success": True,
        "data": {
            "company": CompanyRead.model_validate(company).model_dump(),
            "signals": [_signal_with_evidence(db, s) for s in signals],
            "pain_points": [PainPointRead.model_validate(p).model_dump() for p in pain_points],
            "opportunities": [
                {**OpportunityRead.model_validate(o).model_dump(), "evidence_count": evidence_counts.get(o.id, 0)}
                for o in opportunities
            ],
            "source_records": [_record_view(db, r) for r in records],
            "counts": {
                "signals": len(signals),
                "pain_points": len(pain_points),
                "opportunities": len(opportunities),
                "source_records": len(records),
            },
        },
        "message": None,
    }


def _record_view(db: Session, record: SourceRecord) -> dict:
    data = SourceRecordRead.model_validate(record).model_dump()
    source = db.get(Source, record.source_id)
    data["source"] = {
        "name": source.name,
        "source_type": source.source_type,
        "reliability_grade": source.reliability_grade,
        "reliability_score": source.reliability_score,
    } if source else None
    data["excerpt"] = (record.raw_text or "")[:400] or None
    return data


@router.patch("/{company_id}")
def update_company(company_id: str, payload: CompanyUpdate, db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    write_audit(db, "UPDATE", "company", company.id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(company)
    return {"success": True, "data": CompanyRead.model_validate(company).model_dump(), "message": None}
