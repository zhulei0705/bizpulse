from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.llm_run import LLMRun
from app.schemas.llm_run import LLMRunRead

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/llm-runs")
def list_llm_runs(
    status: str | None = None,
    module: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if status:
        filters.append(LLMRun.status == status)
    if module:
        filters.append(LLMRun.module == module)
    total = db.scalar(select(func.count()).select_from(LLMRun).where(*filters)) or 0
    items = db.scalars(select(LLMRun).where(*filters).order_by(LLMRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [LLMRunRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.get("/audit")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    items = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    data = [{
        "id": x.id, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id,
        "actor": x.actor, "payload_json": x.payload_json, "created_at": x.created_at,
    } for x in items]
    return {"success": True, "data": {"items": data, "total": total, "page": page, "page_size": page_size}, "message": None}
