import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.schemas.signal import SignalCreate, SignalRead
from app.services.audit import write_audit

router = APIRouter(prefix="/signals", tags=["signals"])

MANUAL_SOURCE_TYPE = "MANUAL_ENTRY"


@router.get("")
def list_signals(
    signal_type: str | None = None,
    company_id: str | None = None,
    status: str | None = None,
    fact_or_inference: str | None = None,
    min_confidence: int | None = Query(default=None, ge=0, le=100),
    collected_from: datetime | None = Query(default=None),
    collected_to: datetime | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if signal_type:
        filters.append(Signal.signal_type == signal_type)
    if company_id:
        filters.append(Signal.company_id == company_id)
    if status:
        filters.append(Signal.status == status)
    if fact_or_inference:
        filters.append(Signal.fact_or_inference == fact_or_inference)
    if min_confidence is not None:
        filters.append(Signal.confidence >= min_confidence)
    if collected_from is not None:
        filters.append(Signal.collected_at >= collected_from)
    if collected_to is not None:
        filters.append(Signal.collected_at <= collected_to)
    total = db.scalar(select(func.count()).select_from(Signal).where(*filters)) or 0
    items = db.scalars(select(Signal).where(*filters).order_by(Signal.collected_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    today_new = _today_count(db)
    stats = {"total_signals": total, "today_new": today_new}
    return {
        "success": True,
        "data": {"items": [_view(db, s) for s in items], "total": total, "page": page, "page_size": page_size, "stats": stats},
        "message": None,
    }


def _today_count(db: Session) -> int:
    from app.services.dashboard import start_of_utc_day

    return db.scalar(select(func.count()).select_from(Signal).where(Signal.collected_at >= start_of_utc_day())) or 0


def _view(db: Session, signal: Signal) -> dict:
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
    data["company_name"] = db.scalar(select(Company.company_name).where(Company.id == signal.company_id)) if signal.company_id else None
    return data


def _get_or_create_manual_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.source_type == MANUAL_SOURCE_TYPE))
    if source:
        return source
    source = Source(
        name="人工录入证据",
        source_type=MANUAL_SOURCE_TYPE,
        reliability_grade="B",
        reliability_score=60,
        enabled=True,
        collector_type="manual",
        notes="人工创建商业信号时提交的证据 URL。",
    )
    db.add(source)
    db.flush()
    return source


@router.post("")
def create_signal(payload: SignalCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=422, detail="company_id does not exist")

    if payload.source_record_id:
        record = db.get(SourceRecord, payload.source_record_id)
        if not record:
            raise HTTPException(status_code=422, detail="source_record_id does not exist")
    else:
        # 人工信号：为证据 URL 建立 SourceRecord，保证所有信号可追溯
        source = _get_or_create_manual_source(db)
        url = payload.evidence_url.strip()
        title = payload.evidence_title or payload.title
        fingerprint = hashlib.sha256(f"{url}\n{title}\n{payload.description or ''}".encode("utf-8")).hexdigest()
        record = db.scalar(select(SourceRecord).where(SourceRecord.source_id == source.id, SourceRecord.content_hash == fingerprint))
        if not record:
            record = SourceRecord(
                source_id=source.id,
                company_id=payload.company_id,
                url=url,
                title=title,
                raw_text=payload.description,
                content_hash=fingerprint,
                source_reliability=source.reliability_grade,
                metadata_json={"collected_via": "manual_signal", "note": "人工创建信号时提交的证据"},
            )
            db.add(record)
            db.flush()
        payload.source_record_id = record.id

    data = payload.model_dump(exclude={"evidence_url", "evidence_title"})
    signal = Signal(**data)
    db.add(signal)
    db.flush()
    write_audit(db, "CREATE", "signal", signal.id, {"signal_type": signal.signal_type, "company_id": signal.company_id})
    db.commit()
    db.refresh(signal)
    return {"success": True, "data": _view(db, signal), "message": None}


@router.get("/{signal_id}")
def get_signal(signal_id: str, db: Session = Depends(get_db)) -> dict:
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"success": True, "data": _view(db, signal), "message": None}
