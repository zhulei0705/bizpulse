from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard import dashboard_summary
from app.services.radar import RadarFilters, build_radar_summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    return {"success": True, "data": dashboard_summary(db), "message": None}


@router.get("/radar/summary")
def radar_summary(
    industry: str | None = Query(default=None),
    country: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    min_evidence: int | None = Query(default=None, ge=0),
    min_evidence_score: int | None = Query(default=None, ge=0, le=100),
    signal_type: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """机会雷达总览：筛选参数直接作用于 SQL 聚合（禁止前端过滤）。"""
    filters = RadarFilters(
        industry=industry, country=country, grade=grade, min_score=min_score,
        min_evidence=min_evidence, min_evidence_score=min_evidence_score,
        signal_type=signal_type, days=days,
    )
    return {"success": True, "data": build_radar_summary(db, filters), "message": None}
