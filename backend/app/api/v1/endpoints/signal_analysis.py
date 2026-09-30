"""T04 商业信号分析 API：

- POST /source-records/{id}/analyze-signals   单条记录信号分析
- POST /jobs/analyze-signals                  批量分析（复用 Job 框架，job_type=ANALYZE）
- GET  /signal-candidates                     候选列表（含结构化/证据/原因）
- POST /signal-candidates/{id}/approve|reject 人工审核
- POST /signals/{id}/approve|reject           正式 Signal 审核（写 before/after）
- GET  /signals/{id}                          详情增强（fact/inference、evidences、置信度解释）
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyzers.extractor import ExtractStats, approve_candidate_manually, run_extractor
from app.db.session import get_db
from app.models.company import Company
from app.models.job import CollectionJob
from app.models.signal import Signal, SignalCandidate, SignalEvidence
from app.models.source import Source, SourceRecord
from app.services.audit import write_audit

router = APIRouter(tags=["signal-analysis"])


class ReviewNote(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# 信号分析
# ---------------------------------------------------------------------------

@router.post("/source-records/{record_id}/analyze-signals")
def analyze_record_signals(record_id: str, payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    record = db.get(SourceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Source record not found")
    force = bool(payload and payload.note == "force")
    stats: ExtractStats = run_extractor(db, record, force=force)
    from dataclasses import asdict
    return {"success": True, "data": asdict(stats), "message": None}


@router.post("/jobs/analyze-signals")
def analyze_signals_job(payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    """批量分析：处理未分析或内容变化的最新记录（不重复分析 hash 未变数据）。"""
    limit = 100
    records = db.scalars(
        select(SourceRecord).where(SourceRecord.is_latest.is_(True), SourceRecord.parse_status == "OK").order_by(SourceRecord.collected_at.desc()).limit(limit)
    ).all()
    job = CollectionJob(name="批量信号分析", job_type="ANALYZE", status="RUNNING", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    totals = {"total": len(records), "processed": 0, "signals_detected": 0, "approved": 0, "review_required": 0, "merged": 0, "failed": 0}
    run_log: list[dict] = []
    for record in records:
        try:
            stats = run_extractor(db, record)
            totals["processed"] += 1
            totals["signals_detected"] += stats.candidates_detected
            totals["approved"] += stats.auto_approved
            totals["review_required"] += stats.review_required
            totals["merged"] += stats.merged
            run_log.append({"record_id": record.id, "url": record.url, "detected": stats.candidates_detected, "approved": stats.auto_approved, "review": stats.review_required, "merged": stats.merged, "skipped_reason": stats.errors[0] if stats.errors else None})
        except Exception as exc:  # noqa: BLE001
            totals["failed"] += 1
            run_log.append({"record_id": record.id, "url": record.url, "error": str(exc)[:200]})
    job.items_found = totals["total"]
    job.items_created = totals["signals_detected"]
    job.items_skipped = totals["merged"]
    job.error_count = totals["failed"]
    job.finished_at = datetime.now(timezone.utc)
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds() if job.started_at else None
    job.status = "PARTIAL_SUCCESS" if totals["failed"] else "SUCCESS"
    job.run_log_json = run_log
    job.query = f"stats:{totals}"
    db.commit()
    return {"success": True, "data": {"job_id": job.id, **totals}, "message": None}


# ---------------------------------------------------------------------------
# 候选审核
# ---------------------------------------------------------------------------

def _candidate_view(db: Session, c: SignalCandidate) -> dict:
    record = db.get(SourceRecord, c.source_record_id)
    source = db.get(Source, record.source_id) if record else None
    company_name = db.scalar(select(Company.company_name).where(Company.id == c.company_id)) if c.company_id else None
    return {
        "id": c.id, "company_id": c.company_id, "company_name": company_name,
        "source_record_id": c.source_record_id, "url": record.url if record else None,
        "title": record.title if record else None,
        "source_name": source.name if source else None,
        "reliability_grade": source.reliability_grade if source else None,
        "candidate_type": c.candidate_type, "evidence_text": c.evidence_text,
        "start_offset": c.start_offset, "end_offset": c.end_offset,
        "rule_confidence": c.rule_confidence, "llm_confidence": c.llm_confidence,
        "final_confidence": c.final_confidence, "status": c.status, "reason": c.reason,
        "structured": c.structured_json, "fact_summary": c.fact_summary,
        "inference_summary": c.inference_summary, "prompt_version": c.prompt_version,
        "fingerprint": c.fingerprint, "signal_id": c.signal_id,
        "created_at": c.created_at,
    }


@router.get("/signal-candidates")
def list_candidates(
    status: str | None = None,
    company_id: str | None = None,
    source_record_id: str | None = None,
    candidate_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if status:
        filters.append(SignalCandidate.status == status)
    if company_id:
        filters.append(SignalCandidate.company_id == company_id)
    if source_record_id:
        filters.append(SignalCandidate.source_record_id == source_record_id)
    if candidate_type:
        filters.append(SignalCandidate.candidate_type == candidate_type)
    total = db.scalar(select(func.count()).select_from(SignalCandidate).where(*filters)) or 0
    items = db.scalars(select(SignalCandidate).where(*filters).order_by(SignalCandidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [_candidate_view(db, c) for c in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("/signal-candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str, payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(SignalCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status in {"APPROVED", "MERGED", "REJECTED"}:
        raise HTTPException(status_code=409, detail=f"候选已处理（{candidate.status}）")
    try:
        signal = approve_candidate_manually(db, candidate, note=payload.note if payload else None, reject=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": {"candidate_id": candidate.id, "signal_id": signal.id if signal else None, "status": "APPROVED"}, "message": None}


@router.post("/signal-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(SignalCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status in {"APPROVED", "MERGED"}:
        raise HTTPException(status_code=409, detail=f"候选已处理（{candidate.status}）")
    approve_candidate_manually(db, candidate, note=payload.note if payload else None, reject=True)
    return {"success": True, "data": {"candidate_id": candidate.id, "status": "REJECTED"}, "message": None}


# ---------------------------------------------------------------------------
# 正式 Signal 审核（approve / reject，写 before/after）
# ---------------------------------------------------------------------------

def _signal_evidences_view(db: Session, signal_id: str) -> list[dict]:
    rows = db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == signal_id)).all()
    result = []
    for e in rows:
        record = db.get(SourceRecord, e.source_record_id)
        source = db.get(Source, record.source_id) if record else None
        result.append({
            "id": e.id, "source_record_id": e.source_record_id, "quoted_text": e.quoted_text,
            "start_offset": e.start_offset, "end_offset": e.end_offset,
            "evidence_type": e.evidence_type, "confidence": e.confidence,
            "verification_status": e.verification_status,
            "url": record.url if record else None, "title": record.title if record else None,
            "source_name": source.name if source else None,
            "reliability_grade": source.reliability_grade if source else None,
            "published_at": record.published_at if record else None,
            "collected_at": record.collected_at if record else None,
        })
    return result


@router.post("/signals/{signal_id}/approve")
def approve_signal(signal_id: str, payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    before = {"status": signal.status, "verification_status": signal.verification_status}
    signal.status = "APPROVED"
    signal.verification_status = "VERIFIED"
    signal.last_verified_at = datetime.now(timezone.utc)
    write_audit(db, "SIGNAL_APPROVED", "signal", signal.id, {"before": before, "after": {"status": "APPROVED"}, "note": payload.note if payload else None})
    db.commit()
    return {"success": True, "data": {"id": signal.id, "status": "APPROVED"}, "message": None}


@router.post("/signals/{signal_id}/reject")
def reject_signal(signal_id: str, payload: ReviewNote | None = None, db: Session = Depends(get_db)) -> dict:
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    before = {"status": signal.status}
    signal.status = "REJECTED"
    write_audit(db, "SIGNAL_REJECTED", "signal", signal.id, {"before": before, "after": {"status": "REJECTED"}, "note": payload.note if payload else None})
    db.commit()
    return {"success": True, "data": {"id": signal.id, "status": "REJECTED"}, "message": None}


@router.get("/signals/{signal_id}/evidences")
def signal_evidences(signal_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Signal, signal_id):
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"success": True, "data": {"items": _signal_evidences_view(db, signal_id)}, "message": None}
