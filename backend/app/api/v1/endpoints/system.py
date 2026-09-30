from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {
        "success": True,
        "data": {"status": "ok", "service": "BizPulse", "environment": settings.app_env},
        "message": None,
    }


@router.get("/system/info")
def system_info(db: Session = Depends(get_db)) -> dict:
    database = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "disconnected"
    return {
        "success": True,
        "data": {
            "name": settings.app_display_name,
            "version": settings.app_version,
            "environment": settings.app_env,
            "database": database,
            "no_fake_data": settings.no_fake_data,
        },
        "message": None,
    }
