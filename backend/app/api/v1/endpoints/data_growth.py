"""T08 数据增长报告 API：summary / quality / gap（只读统计，无假数据）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.company_quality import source_coverage
from app.services.data_growth import data_growth_gap, data_growth_quality, data_growth_summary

router = APIRouter(prefix="/data-growth", tags=["data-growth"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    return {"success": True, "data": data_growth_summary(db), "message": None}


@router.get("/quality")
def quality(db: Session = Depends(get_db)) -> dict:
    return {"success": True, "data": data_growth_quality(db), "message": None}


@router.get("/gap")
def gap(db: Session = Depends(get_db)) -> dict:
    return {"success": True, "data": data_growth_gap(db), "message": None}


@router.get("/coverage/{company_id}")
def coverage(company_id: str, db: Session = Depends(get_db)) -> dict:
    return {"success": True, "data": source_coverage(db, company_id), "message": None}


@router.get("/funnel")
def funnel(db: Session = Depends(get_db)) -> dict:
    """T08.2 数据漏斗（任务书三十三）：真实聚合，不补数据。"""
    from app.services.company_coverage import data_funnel

    return {"success": True, "data": data_funnel(db), "message": None}


@router.get("/scenarios")
def scenarios(db: Session = Depends(get_db)) -> dict:
    """T08.2 商业场景分布（任务书三十/三十二）：仅 Approved + 可行动信号。"""
    from app.services.company_coverage import scenario_distribution

    return {"success": True, "data": {"distribution": scenario_distribution(db)}, "message": None}
