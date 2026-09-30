from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.source import Source, SourceRecord

router = APIRouter(prefix="/source-records", tags=["source-records"])


def _serialize_record(db: Session, record: SourceRecord) -> dict:
    from app.schemas.source import SourceRecordRead

    data = SourceRecordRead.model_validate(record).model_dump()
    source = db.get(Source, record.source_id)
    data["source"] = {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "reliability_grade": source.reliability_grade,
        "reliability_score": source.reliability_score,
    } if source else None
    data["excerpt"] = (record.raw_text or "")[:400] or None
    data["raw_text"] = record.raw_text
    data["canonical_url"] = record.canonical_url
    data["version_number"] = record.version_number
    data["is_latest"] = record.is_latest
    data["parent_record_id"] = record.parent_record_id
    data["parse_status"] = record.parse_status
    data["error_message"] = record.error_message
    data["checked_at"] = record.checked_at
    data["company_resolve_status"] = record.company_resolve_status
    data["company"] = None
    if record.company_id:
        company = db.get(Company, record.company_id)
        if company:
            data["company"] = {"id": company.id, "company_name": company.company_name, "domain": company.domain}
    # 版本历史（同 canonical_url 全链，按版本倒序）
    versions = db.scalars(
        select(SourceRecord)
        .where(SourceRecord.source_id == record.source_id, SourceRecord.canonical_url == record.canonical_url)
        .order_by(SourceRecord.version_number.desc())
    ).all() if record.canonical_url else [record]
    data["versions"] = [
        {
            "id": v.id, "version_number": v.version_number, "is_latest": v.is_latest,
            "collected_at": v.collected_at, "content_hash": v.content_hash,
            "title": v.title, "http_status": v.http_status, "parse_status": v.parse_status,
        } for v in versions
    ]
    return data


@router.get("")
def list_source_records(
    company_id: str | None = None,
    source_id: str | None = None,
    is_latest: bool | None = Query(default=True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if company_id:
        filters.append(SourceRecord.company_id == company_id)
    if source_id:
        filters.append(SourceRecord.source_id == source_id)
    if is_latest is not None:
        filters.append(SourceRecord.is_latest.is_(is_latest))
    total = db.scalar(select(func.count()).select_from(SourceRecord).where(*filters)) or 0
    items = db.scalars(
        select(SourceRecord).where(*filters).order_by(SourceRecord.collected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {"items": [_serialize_record(db, x) for x in items], "total": total, "page": page, "page_size": page_size},
        "message": None,
    }


@router.get("/{record_id}")
def get_source_record(record_id: str, db: Session = Depends(get_db)) -> dict:
    record = db.get(SourceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Source record not found")
    return {"success": True, "data": _serialize_record(db, record), "message": None}
