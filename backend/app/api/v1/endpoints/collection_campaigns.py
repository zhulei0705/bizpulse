"""T08 采集战役 API：数据扩充计划（只做采集计划；企业入正式库必须过真实性 Gate）。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import CAMPAIGN_STATUSES
from app.db.session import get_db
from app.models.company import CollectionCampaign
from app.schemas.common import ORMModel
from app.services.audit import write_audit
from app.services.campaign_runner import run_campaign

router = APIRouter(prefix="/collection-campaigns", tags=["collection-campaigns"])


class CampaignCreate(ORMModel):
    name: str = Field(min_length=1, max_length=300)
    market: str | None = None
    keywords: list[str] = []
    source_types: list[str] = []
    seed_urls: list[str] = []
    target_company_count: int = Field(default=30, ge=1, le=300)


class CampaignRead(ORMModel):
    id: str
    name: str
    market: str | None
    keywords: list
    source_types: list
    seed_urls: list
    target_company_count: int
    status: str
    progress: dict = {}
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _serialize(c: CollectionCampaign) -> dict:
    data = CampaignRead.model_validate(c).model_dump()
    data["progress"] = c.progress_json or {}
    return data


@router.get("")
def list_campaigns(status: str | None = None, db: Session = Depends(get_db)) -> dict:
    filters = [CollectionCampaign.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(CollectionCampaign).where(*filters)) or 0
    items = db.scalars(select(CollectionCampaign).where(*filters).order_by(CollectionCampaign.updated_at.desc())).all()
    return {"success": True, "data": {"items": [_serialize(x) for x in items], "total": total}, "message": None}


@router.post("")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> dict:
    if not payload.seed_urls:
        raise HTTPException(status_code=422, detail="seed_urls 必填：战役必须基于真实公开来源页（发现来源可追溯）")
    campaign = CollectionCampaign(**payload.model_dump(), status="DRAFT", progress_json={})
    db.add(campaign)
    db.flush()
    write_audit(db, "CREATE", "collection_campaign", campaign.id, {
        "name": campaign.name, "market": campaign.market, "seed_urls": campaign.seed_urls,
    })
    db.commit()
    db.refresh(campaign)
    return {"success": True, "data": _serialize(campaign), "message": None}


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(CollectionCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"success": True, "data": _serialize(campaign), "message": None}


@router.post("/{campaign_id}/run")
def run(campaign_id: str, payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    """执行采集战役（真实网络抓取；单条公告失败不回滚整批；Signal 一律待人工批准）。"""
    campaign = db.get(CollectionCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status in {"COMPLETED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail=f"战役已结束（{campaign.status}）")
    max_notices = int((payload or {}).get("max_notices") or 40)
    result = run_campaign(db, campaign, max_notices=max_notices)
    return {"success": True, "data": result, "message": None}


@router.get("/{campaign_id}/progress")
def campaign_progress(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(CollectionCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {
        "success": True,
        "data": {
            "campaign_id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "target_company_count": campaign.target_company_count,
            "progress": campaign.progress_json or {},
        },
        "message": None,
    }
