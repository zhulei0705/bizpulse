from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company, CompanyContact
from app.models.source import SourceRecord
from app.schemas.contact import CompanyContactCreate, CompanyContactRead
from app.services.audit import write_audit

router = APIRouter(prefix="/companies/{company_id}/contacts", tags=["company-contacts"])


@router.get("")
def list_contacts(company_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    items = db.scalars(select(CompanyContact).where(CompanyContact.company_id == company_id).order_by(CompanyContact.confidence.desc())).all()
    return {"success": True, "data": [CompanyContactRead.model_validate(x).model_dump() for x in items], "message": None}


@router.post("")
def create_contact(company_id: str, payload: CompanyContactCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    if payload.source_record_id and not db.get(SourceRecord, payload.source_record_id):
        raise HTTPException(status_code=422, detail="source_record_id does not exist")
    contact = CompanyContact(company_id=company_id, **payload.model_dump())
    db.add(contact)
    db.flush()
    write_audit(db, "CREATE", "company_contact", contact.id, {"company_id": company_id})
    db.commit()
    db.refresh(contact)
    return {"success": True, "data": CompanyContactRead.model_validate(contact).model_dump(), "message": None}
