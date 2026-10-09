"""T05 机会候选 API：

- GET  /opportunity-candidates                    候选列表（状态/企业筛选）
- GET  /opportunity-candidates/{id}               候选详情（评分明细/证据/风险/验证问题）
- POST /companies/{id}/analyze-opportunities      单企业机会分析（输入 hash 未变自动跳过）
- POST /jobs/analyze-opportunities                批量分析（只分析有新 Approved Signal 的企业）
- POST /opportunity-candidates/{id}/approve       人工通过 → 转正式 Opportunity（EvidenceGate 强制）
- POST /opportunity-candidates/{id}/reject        人工驳回（必须填写驳回原因枚举）
- POST /opportunity-candidates/{id}/need-more-evidence  人工标记证据不足
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyzers.opportunity.dedup import find_active_candidate
from app.analyzers.opportunity.generator import analyze_companies_batch, analyze_company_opportunities
from app.core.constants import OPPORTUNITY_REJECT_REASONS, PAIN_CATEGORIES
from app.db.session import get_db
from app.models.company import Company
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.models.opportunity_candidate import OpportunityCandidate
from app.services.audit import write_audit
from app.services.scoring import EvidenceGateError, evidence_gate

router = APIRouter(tags=["opportunity-candidates"])


class AnalyzeRequest(BaseModel):
    force: bool = False


class CandidateReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    reject_reason: str | None = None

    @model_validator(mode="after")
    def _validate_reason(self) -> "CandidateReviewRequest":
        if self.reject_reason and self.reject_reason not in OPPORTUNITY_REJECT_REASONS:
            raise ValueError(f"reject_reason 必须是 {sorted(OPPORTUNITY_REJECT_REASONS)} 之一")
        return self


def _serialize_candidate(candidate: OpportunityCandidate, company_name: str | None) -> dict:
    return {
        "id": candidate.id,
        "company_id": candidate.company_id,
        "company_name": company_name,
        "bundle_id": candidate.bundle_id,
        "pain_point_id": candidate.pain_point_id,
        "title": candidate.title,
        "problem_hypothesis": candidate.problem_hypothesis,
        "solution_hypothesis": candidate.solution_hypothesis,
        "value_hypothesis": candidate.value_hypothesis,
        "trigger_summary": candidate.trigger_summary,
        "why_now": candidate.why_now,
        "evidence_summary": candidate.evidence_summary,
        "recommended_next_action": candidate.recommended_next_action,
        "signal_ids": candidate.signal_ids_json,
        "pain_category": candidate.pain_category,
        "pain_category_label": PAIN_CATEGORIES.get(candidate.pain_category or "", candidate.pain_category),
        "solution_category": candidate.solution_category,
        "pain_score": candidate.pain_score,
        "budget_score": candidate.budget_score,
        "intent_score": candidate.intent_score,
        "urgency_score": candidate.urgency_score,
        "agent_fit_score": candidate.agent_fit_score,
        "reachability_score": candidate.reachability_score,
        "evidence_score": candidate.evidence_score,
        "total_score": round(candidate.total_score, 1),
        "grade": candidate.grade,
        "grade_cap_reason": candidate.grade_cap_reason,
        "confidence": candidate.confidence,
        "score_breakdown": candidate.score_breakdown_json,
        "risk_notes": candidate.risk_notes,
        "validation_questions": candidate.validation_questions,
        "evidence_refs": candidate.evidence_refs_json,
        "contradicting_evidence": candidate.contradicting_evidence_json,
        "status": candidate.status,
        "generated_by": candidate.generated_by,
        "prompt_version": candidate.prompt_version,
        "analysis_input_hash": candidate.analysis_input_hash,
        "fingerprint": candidate.fingerprint,
        "reject_reason": candidate.reject_reason,
        "review_note": candidate.review_note,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "opportunity_id": candidate.opportunity_id,
        "created_at": candidate.created_at.isoformat(),
        "updated_at": candidate.updated_at.isoformat(),
    }


@router.get("/opportunity-candidates")
def list_candidates(
    status: str | None = None,
    company_id: str | None = None,
    pain_category: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if status:
        filters.append(OpportunityCandidate.status == status)
    if company_id:
        filters.append(OpportunityCandidate.company_id == company_id)
    if pain_category:
        filters.append(OpportunityCandidate.pain_category == pain_category)
    if min_score is not None:
        filters.append(OpportunityCandidate.total_score >= min_score)
    total = db.scalar(select(func.count()).select_from(OpportunityCandidate).where(*filters)) or 0
    items = db.scalars(
        select(OpportunityCandidate).where(*filters)
        .order_by(OpportunityCandidate.total_score.desc(), OpportunityCandidate.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    names = dict(db.execute(select(Company.id, Company.company_name)).all())
    counts = {
        "review": db.scalar(select(func.count()).select_from(OpportunityCandidate).where(OpportunityCandidate.status == "REVIEW")) or 0,
        "need_more_evidence": db.scalar(select(func.count()).select_from(OpportunityCandidate).where(OpportunityCandidate.status == "NEED_MORE_EVIDENCE")) or 0,
        "approved": db.scalar(select(func.count()).select_from(OpportunityCandidate).where(OpportunityCandidate.status == "APPROVED")) or 0,
        "converted": db.scalar(select(func.count()).select_from(OpportunityCandidate).where(OpportunityCandidate.status == "CONVERTED")) or 0,
    }
    return {
        "success": True,
        "data": {"items": [_serialize_candidate(c, names.get(c.company_id)) for c in items],
                 "total": total, "page": page, "page_size": page_size, "counts": counts},
        "message": None,
    }


@router.get("/opportunity-candidates/{candidate_id}")
def get_candidate(candidate_id: str, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(OpportunityCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    company_name = db.scalar(select(Company.company_name).where(Company.id == candidate.company_id))
    data = _serialize_candidate(candidate, company_name)
    # 附带信号与来源（详情可回溯）
    from app.models.signal import Signal
    from app.models.source import Source, SourceRecord
    signals_view = []
    for signal_id in candidate.signal_ids_json or []:
        signal = db.get(Signal, signal_id)
        if not signal:
            continue
        record = db.get(SourceRecord, signal.source_record_id)
        source = db.get(Source, record.source_id) if record else None
        signals_view.append({
            "id": signal.id,
            "signal_type": signal.signal_type,
            "title": signal.title,
            "fact_summary": signal.fact_summary,
            "inference_summary": signal.inference_summary,
            "confidence": signal.confidence,
            "status": signal.status,
            "url": record.url if record else None,
            "source_name": source.name if source else None,
            "reliability_grade": source.reliability_grade if source else None,
            "collected_at": signal.collected_at.isoformat(),
        })
    data["signals"] = signals_view
    return {"success": True, "data": data, "message": None}


@router.post("/companies/{company_id}/analyze-opportunities")
def analyze_company(company_id: str, payload: AnalyzeRequest | None = None, db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    stats = analyze_company_opportunities(db, company_id, force=bool(payload and payload.force))
    return {
        "success": True,
        "data": {
            "company_id": company_id,
            "status": stats.status,
            "reason": stats.reason,
            "candidates_created": stats.candidates_created,
            "candidates_updated": stats.candidates_updated,
            "need_more_evidence": stats.need_more_evidence,
            "bundles": stats.bundles,
            "llm_used": stats.llm_used,
        },
        "message": None,
    }


@router.post("/jobs/analyze-opportunities")
def analyze_opportunities_job(db: Session = Depends(get_db)) -> dict:
    """批量分析：只分析有已批准 Signal 的企业；输入未变跳过；顺带执行 STALE 清扫。"""
    result = analyze_companies_batch(db)
    return {"success": True, "data": result, "message": None}


# ---------------------------------------------------------------------------
# 候选人工审核
# ---------------------------------------------------------------------------

def _convert_candidate(db: Session, candidate: OpportunityCandidate, note: str | None) -> Opportunity:
    """候选 → 正式 Opportunity。EvidenceGate 硬门槛：无证据禁止转换。"""
    evidence_count = len(candidate.evidence_refs_json or [])
    from app.models.signal import Signal
    from app.models.source import SourceRecord
    from app.services.evidence_integrity import signal_issues,record_issues
    for ref in candidate.evidence_refs_json or []:
        signal=db.get(Signal,ref.get('signal_id')) if ref.get('signal_id') else None
        record=db.get(SourceRecord,ref.get('source_record_id')) if ref.get('source_record_id') else None
        if (signal and signal_issues(db,signal)) or (ref.get('source_record_id') and record_issues(record)):
            raise HTTPException(status_code=422,detail='INVALID_EVIDENCE：候选引用的来源已隔离')
    _, cap_reason = evidence_gate(evidence_count, candidate.evidence_score)

    scored_grade = candidate.grade
    if cap_reason and candidate.grade in {"S", "A"}:
        scored_grade = "B" if cap_reason == "LOW_EVIDENCE" else scored_grade

    opportunity = Opportunity(
        company_id=candidate.company_id,
        market_id=candidate.market_id,
        pain_point_id=candidate.pain_point_id,
        candidate_id=candidate.id,
        title=candidate.title,
        problem=candidate.problem_hypothesis,
        solution=candidate.solution_hypothesis,
        value_proposition=candidate.value_hypothesis,
        trigger_event=candidate.trigger_summary,
        why_now=candidate.why_now,
        risk_notes=candidate.risk_notes,
        validation_questions=candidate.validation_questions,
        score_breakdown_json=candidate.score_breakdown_json,
        grade_cap_reason=candidate.grade_cap_reason or cap_reason,
        recommended_next_action=candidate.recommended_next_action,
        fingerprint=candidate.fingerprint,
        analysis_input_hash=candidate.analysis_input_hash,
        last_signal_at=candidate.last_signal_at,
        last_evidence_at=candidate.last_evidence_at,
        pain_score=candidate.pain_score,
        budget_score=candidate.budget_score,
        intent_score=candidate.intent_score,
        urgency_score=candidate.urgency_score,
        agent_fit_score=candidate.agent_fit_score,
        reachability_score=candidate.reachability_score,
        evidence_score=candidate.evidence_score,
        total_score=candidate.total_score,
        grade=scored_grade,
        confidence=candidate.confidence,
        stage="REVIEW",
        status="ACTIVE",
        review_status="PENDING",
    )
    db.add(opportunity)
    db.flush()

    from app.models.signal import Signal
    for ref in candidate.evidence_refs_json or []:
        signal = db.get(Signal, ref.get("signal_id")) if ref.get("signal_id") else None
        db.add(OpportunityEvidence(
            opportunity_id=opportunity.id,
            source_record_id=ref.get("source_record_id"),
            signal_id=ref.get("signal_id"),
            evidence_type="SIGNAL",
            evidence_excerpt=ref.get("excerpt"),
            polarity=ref.get("polarity", "SUPPORTING"),
            source_grade=ref.get("grade"),
        ))
        if signal is not None:
            opportunity.primary_signal_id = opportunity.primary_signal_id or signal.id
    db.flush()
    return opportunity


@router.post("/opportunity-candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str, payload: CandidateReviewRequest | None = None, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(OpportunityCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status in {"APPROVED", "REJECTED", "CONVERTED"}:
        raise HTTPException(status_code=409, detail=f"候选已处理（{candidate.status}）")

    note = payload.note if payload else None
    before = {"status": candidate.status, "grade": candidate.grade}
    try:
        opportunity = _convert_candidate(db, candidate, note)
    except EvidenceGateError as exc:
        # Evidence Count = 0：禁止生成正式机会 → 标记证据不足
        candidate.status = "NEED_MORE_EVIDENCE"
        candidate.review_note = note or str(exc)
        write_audit(db, "CANDIDATE_CONVERT_BLOCKED", "opportunity_candidate", candidate.id, {"reason": str(exc)})
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    candidate.status = "CONVERTED"
    candidate.review_note = note
    candidate.reviewed_by = "local-user"
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.opportunity_id = opportunity.id
    write_audit(db, "CANDIDATE_APPROVED", "opportunity_candidate", candidate.id, {
        "before": before, "after": {"status": "CONVERTED", "opportunity_id": opportunity.id}, "note": note,
    })
    write_audit(db, "CREATE", "opportunity", opportunity.id, {
        "via": "candidate_convert", "candidate_id": candidate.id,
        "total_score": opportunity.total_score, "grade": opportunity.grade,
    })
    db.commit()
    return {
        "success": True,
        "data": {"candidate_id": candidate.id, "status": candidate.status, "opportunity_id": opportunity.id},
        "message": None,
    }


@router.post("/opportunity-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, payload: CandidateReviewRequest, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(OpportunityCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status in {"APPROVED", "REJECTED", "CONVERTED"}:
        raise HTTPException(status_code=409, detail=f"候选已处理（{candidate.status}）")
    reason = payload.reject_reason or "OTHER"
    before = {"status": candidate.status}
    candidate.status = "REJECTED"
    candidate.reject_reason = reason
    candidate.review_note = payload.note
    candidate.reviewed_by = "local-user"
    candidate.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, "CANDIDATE_REJECTED", "opportunity_candidate", candidate.id, {
        "before": before, "after": {"status": "REJECTED", "reject_reason": reason},
        "note": payload.note,
    })
    db.commit()
    return {"success": True, "data": {"candidate_id": candidate.id, "status": "REJECTED", "reject_reason": reason}, "message": None}


@router.post("/opportunity-candidates/{candidate_id}/need-more-evidence")
def candidate_need_more_evidence(candidate_id: str, payload: CandidateReviewRequest | None = None, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(OpportunityCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status in {"APPROVED", "REJECTED", "CONVERTED"}:
        raise HTTPException(status_code=409, detail=f"候选已处理（{candidate.status}）")
    before = {"status": candidate.status}
    candidate.status = "NEED_MORE_EVIDENCE"
    candidate.review_note = payload.note if payload else None
    candidate.reviewed_by = "local-user"
    candidate.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, "CANDIDATE_NEED_MORE_EVIDENCE", "opportunity_candidate", candidate.id, {
        "before": before, "after": {"status": "NEED_MORE_EVIDENCE"}, "note": payload.note if payload else None,
    })
    db.commit()
    return {"success": True, "data": {"candidate_id": candidate.id, "status": "NEED_MORE_EVIDENCE"}, "message": None}
