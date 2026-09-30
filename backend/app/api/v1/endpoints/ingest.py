from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.extractor import URLSafetyError
from app.services.ingest import ingest_url

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestURLRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)
    note: str = Field(default="", max_length=2000)


@router.post("/url")
def ingest_by_url(payload: IngestURLRequest, db: Session = Depends(get_db)) -> dict:
    """手动 URL 分析入口：统一走 CollectorAdapter（与数据源采集同一套逻辑）。"""
    try:
        result = ingest_url(db, payload.url, payload.note)
    except URLSafetyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 —— 抓取失败统一转 502
        raise HTTPException(status_code=502, detail=f"网页采集失败：{exc}") from exc
    return {
        "success": True,
        "data": {
            "source_id": result.source_id,
            "source_record_id": result.source_record_id,
            "company_id": result.company_id,
            "signal_ids": result.signal_ids,
            "pain_point_ids": result.pain_point_ids,
            "opportunity_ids": result.opportunity_ids,
            "llm_configured": result.llm_configured,
            "duplicate": result.duplicate,
        },
        "message": result.message,
    }
