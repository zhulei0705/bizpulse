from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import CollectionJob
from app.models.source import Source
from app.schemas.job import JobCreate, JobRead
from app.services.audit import write_audit
from app.services.collector import run_web_collection_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = [CollectionJob.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(CollectionJob).where(*filters)) or 0
    items = db.scalars(select(CollectionJob).where(*filters).order_by(CollectionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [JobRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> dict:
    if payload.source_id and not db.get(Source, payload.source_id):
        raise HTTPException(status_code=422, detail="source_id does not exist")
    job = CollectionJob(**payload.model_dump())
    db.add(job)
    db.flush()
    write_audit(db, "CREATE", "collection_job", job.id, {"name": job.name})
    db.commit()
    db.refresh(job)
    return {"success": True, "data": JobRead.model_validate(job).model_dump(), "message": None}


@router.post("/{job_id}/run")
def run_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(CollectionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "RUNNING":
        raise HTTPException(status_code=409, detail="Job is already running")
    try:
        record = run_web_collection_job(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Collection failed: {exc}") from exc
    write_audit(db, "RUN", "collection_job", job.id, {"source_record_id": record.id})
    db.commit()
    db.refresh(job)
    return {"success": True, "data": {"job": JobRead.model_validate(job).model_dump(), "source_record_id": record.id}, "message": None}
