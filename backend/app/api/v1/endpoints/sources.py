import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source, SourceRecord
from app.schemas.source import SourceCreate, SourceRead, SourceRecordCreate, SourceRecordRead, SourceUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(
    enabled: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = [Source.enabled == enabled] if enabled is not None else []
    total = db.scalar(select(func.count()).select_from(Source).where(*filters)) or 0
    items = db.scalars(select(Source).where(*filters).order_by(Source.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [SourceRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> dict:
    if payload.reliability_grade not in {"A", "B", "C", "D"}:
        raise HTTPException(status_code=422, detail="reliability_grade must be A/B/C/D")
    source = Source(**payload.model_dump())
    db.add(source)
    db.flush()
    write_audit(db, "CREATE", "source", source.id, {"name": source.name})
    db.commit()
    db.refresh(source)
    return {"success": True, "data": SourceRead.model_validate(source).model_dump(), "message": None}


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db)) -> dict:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"success": True, "data": SourceRead.model_validate(source).model_dump(), "message": None}


@router.patch("/{source_id}")
def update_source(source_id: str, payload: SourceUpdate, db: Session = Depends(get_db)) -> dict:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(source, key, value)
    write_audit(db, "UPDATE", "source", source.id, changes)
    db.commit()
    db.refresh(source)
    return {"success": True, "data": SourceRead.model_validate(source).model_dump(), "message": None}


@router.post("/{source_id}/records")
def create_source_record(source_id: str, payload: SourceRecordCreate, db: Session = Depends(get_db)) -> dict:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    fingerprint = payload.content_hash or hashlib.sha256(
        (payload.url + "\n" + (payload.raw_text or "") + "\n" + (payload.title or "")).encode("utf-8")
    ).hexdigest()
    existing = db.scalar(select(SourceRecord).where(SourceRecord.source_id == source_id, SourceRecord.content_hash == fingerprint))
    if existing:
        return {"success": True, "data": SourceRecordRead.model_validate(existing).model_dump(), "message": "duplicate_record_reused"}
    record = SourceRecord(source_id=source_id, content_hash=fingerprint, source_reliability=source.reliability_grade, **payload.model_dump(exclude={"content_hash"}))
    db.add(record)
    db.flush()
    write_audit(db, "CREATE", "source_record", record.id, {"source_id": source_id, "url": record.url})
    db.commit()
    db.refresh(record)
    return {"success": True, "data": SourceRecordRead.model_validate(record).model_dump(), "message": None}
