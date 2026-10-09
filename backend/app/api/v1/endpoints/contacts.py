"""T06 联系人 API：真实联系人只能来自公开信息或用户合法录入（NO_FAKE_CONTACT）。

- VERIFIED_PUBLIC 必须有真实公开来源（source_record_id 或 source_url），否则 422；
- 修改联系人也走同样校验（PATCH /contacts/{id}）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company, CompanyContact
from app.models.source import SourceRecord
from app.schemas.contact import CompanyContactCreate, CompanyContactRead, CompanyContactUpdate
from app.services.audit import write_audit
from app.services.validation import TransitionDenied, validate_contact_verification

router = APIRouter(prefix="/companies/{company_id}/contacts", tags=["company-contacts"])
contact_router = APIRouter(prefix="/contacts", tags=["company-contacts"])


def _normalize(payload: CompanyContactCreate | CompanyContactUpdate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    # 旧字段兼容：verified_public=true 等价 VERIFIED_PUBLIC
    if data.get("verified_public") and not data.get("verification_status"):
        data["verification_status"] = "VERIFIED_PUBLIC"
    data.pop("verified_public", None)
    return data


def _check(db: Session, company_id: str, data: dict) -> str:
    try:
        return validate_contact_verification(
            verification_status=data.get("verification_status"),
            source_record_id=data.get("source_record_id"),
            source_url=data.get("source_url"),
        )
    except TransitionDenied as exc:
        raise exc


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
    data = _normalize(payload)
    if data.get("source_record_id") and not db.get(SourceRecord, data["source_record_id"]):
        raise HTTPException(status_code=422, detail="source_record_id does not exist")
    status = _check(db, company_id, data)
    data["verification_status"] = status
    contact = CompanyContact(company_id=company_id, **data)
    contact.verified_public = status == "VERIFIED_PUBLIC"
    db.add(contact)
    db.flush()
    write_audit(db, "CREATE", "company_contact", contact.id, {
        "company_id": company_id, "verification_status": status,
        "source_type": contact.source_type, "has_source": bool(contact.source_record_id or contact.source_url),
    })
    db.commit()
    db.refresh(contact)
    return {"success": True, "data": CompanyContactRead.model_validate(contact).model_dump(), "message": None}


@contact_router.patch("/{contact_id}")
def update_contact(contact_id: str, payload: CompanyContactUpdate, db: Session = Depends(get_db)) -> dict:
    contact = db.get(CompanyContact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    data = _normalize(payload)
    merged = {
        "verification_status": data.get("verification_status", contact.verification_status),
        "source_record_id": data.get("source_record_id", contact.source_record_id),
        "source_url": data.get("source_url", contact.source_url),
    }
    status = _check(db, contact.company_id, merged)
    data["verification_status"] = status
    before = {k: str(getattr(contact, k, None)) for k in data}
    for key, value in data.items():
        setattr(contact, key, value)
    contact.verified_public = status == "VERIFIED_PUBLIC"
    write_audit(db, "UPDATE", "company_contact", contact.id, {"before": before, "changes": data})
    db.commit()
    db.refresh(contact)
    return {"success": True, "data": CompanyContactRead.model_validate(contact).model_dump(), "message": None}


@contact_router.get("/{contact_id}")
def get_contact(contact_id: str, db: Session = Depends(get_db)) -> dict:
    contact = db.get(CompanyContact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"success": True, "data": CompanyContactRead.model_validate(contact).model_dump(), "message": None}
