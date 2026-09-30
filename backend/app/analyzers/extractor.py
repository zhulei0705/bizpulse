"""SignalExtractor —— 统一信号提取编排（T04）。

流程：SourceRecord → 预处理 → RuleEngine → 候选 → LLM 结构化（可替换/未配置不阻塞）
→ Evidence 原文校验 → Confidence 计算 → 指纹去重/多来源合并 → Candidate 落库
→ 自动批准（confidence≥85 + A/B 来源 + 证据原文可寻）或 REVIEW_REQUIRED。

铁律：
- 每个 Signal/候选必须关联 SourceRecord + 原文 Evidence（无原文不生成）；
- 事实(fact)与推断(inference)分离，推断不得反向成为证据；
- 禁止直接生成 Opportunity（T05 职责）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers import prompts
from app.analyzers.confidence import compute_signal_confidence
from app.analyzers.dedup import compute_signal_fingerprint, find_duplicate_signal, merge_evidence
from app.analyzers.signal_rules import CandidateDraft, run_signal_rules
from app.core.config import settings
from app.llm import get_llm_adapter
from app.models.company import Company
from app.models.signal import Signal, SignalCandidate, SignalEvidence
from app.models.source import Source, SourceRecord
from app.services.audit import write_audit

logger = logging.getLogger(__name__)


@dataclass
class ExtractStats:
    source_record_id: str
    candidates_detected: int = 0
    auto_approved: int = 0
    review_required: int = 0
    merged: int = 0
    rejected_no_evidence: int = 0
    llm_used: bool = False
    errors: list[str] = field(default_factory=list)


def _fingerprint_for(record: SourceRecord, company_id: str | None, signal_type: str, event_text: str) -> str:
    return compute_signal_fingerprint(company_id, signal_type, event_text, record.published_at, record.collected_at)


def _candidate_title(draft: CandidateDraft, record: SourceRecord) -> str:
    label = draft.extra.get("label", draft.candidate_type)
    return f"{label}：{(record.title or record.url)[:60]}"[:500]


def _approve_candidate_into_signal(db: Session, candidate: SignalCandidate, record: SourceRecord, confidence_explanation: dict) -> Signal:
    """候选 → 正式 Signal（含原文 Evidence、fact/inference、生命周期字段）。

    Signal.company_id 为 NOT NULL：无企业关联的候选不允许直接批准（先人工关联企业）。
    """
    if not candidate.company_id:
        raise ValueError("候选未关联企业：请先通过 /source-records/{id}/assign-company 关联企业后再审核")
    company_id = candidate.company_id
    fingerprint = candidate.fingerprint
    signal = Signal(
        company_id=company_id,
        source_record_id=record.id,
        signal_type=candidate.candidate_type,
        title=_candidate_title_from(candidate, record),
        description=candidate.evidence_text,
        published_at=record.published_at,
        collected_at=datetime.now(timezone.utc),
        confidence=candidate.final_confidence,
        reliability_score=_source_score(db, record.source_id),
        status="APPROVED",
        fact_or_inference="FACT",
        fact_summary=candidate.fact_summary or (candidate.evidence_text or "")[:300],
        inference_summary=candidate.inference_summary,
        signal_fingerprint=fingerprint,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        created_by="LLM" if candidate.llm_confidence is not None else "RULE",
        prompt_version=candidate.prompt_version,
        change_type=None,
        change_value=None,
        payload_json={
            "confidence_explanation": confidence_explanation,
            "rule_confidence": candidate.rule_confidence,
            "llm_confidence": candidate.llm_confidence,
            "structured": candidate.structured_json,
            "source_record_version": record.version_number,
        },
    )
    db.add(signal)
    db.flush()
    db.add(SignalEvidence(
        signal_id=signal.id,
        source_record_id=record.id,
        quoted_text=(candidate.evidence_text or "")[:2000],
        start_offset=candidate.start_offset,
        end_offset=candidate.end_offset,
        confidence=candidate.final_confidence,
    ))
    candidate.status = "APPROVED"
    candidate.signal_id = signal.id
    candidate.reason = (candidate.reason or "") + " | 自动批准：置信度与证据校验通过"
    if company_id:
        write_audit(db, "SIGNAL_AUTO_APPROVED", "signal", signal.id, {
            "candidate_id": candidate.id, "confidence": signal.confidence,
            "fingerprint": fingerprint, "source_record_id": record.id,
        })
    return signal


def _candidate_title_from(candidate: SignalCandidate, record: SourceRecord) -> str:
    structured = candidate.structured_json or {}
    what = structured.get("what") or structured.get("object")
    action = structured.get("action")
    parts = [p for p in (action, what) if p]
    core = " ".join(parts) if parts else (candidate.fact_summary or candidate.candidate_type)
    return f"{core[:80]}：{(record.title or record.url)[:40]}"[:500]


def _source_score(db: Session, source_id: str) -> int:
    source = db.get(Source, source_id)
    return int(source.reliability_score) if source else 50


def _source_grade(db: Session, source_id: str) -> str:
    source = db.get(Source, source_id)
    return (source.reliability_grade if source else "C") or "C"


def _evidence_in_source(evidence_text: str | None, source_text: str) -> bool:
    """Evidence 原文校验：LLM 返回的片段必须可在原文中找到（忽略首尾空白）。"""
    if not evidence_text:
        return False
    needle = " ".join(evidence_text.split())
    if not needle:
        return False
    if needle in source_text:
        return True
    # 容忍换行差异
    flattened = " ".join(source_text.split())
    return needle in flattened


def run_extractor(db: Session, record: SourceRecord, *, force: bool = False) -> ExtractStats:
    """对单条 SourceRecord 执行信号提取（幂等：已分析且 hash 未变的记录默认跳过）。"""
    stats = ExtractStats(source_record_id=record.id)
    source_text = record.raw_text or ""
    if not source_text.strip():
        stats.errors.append("正文为空，跳过分析")
        return stats

    analyzed_hashes = (record.metadata_json or {}).get("signal_analysis_hashes") or []
    current_hash = record.content_hash
    if not force and current_hash in analyzed_hashes:
        stats.errors.append("内容未变化且已分析，跳过")
        return stats

    source = db.get(Source, record.source_id)
    source_type = source.source_type if source else None
    company = db.get(Company, record.company_id) if record.company_id else None

    # 1) Rule Engine → 候选草稿
    drafts = run_signal_rules(source_text, source_type)
    stats.candidates_detected = len(drafts)

    # 2) LLM 结构化（可替换；未配置不阻塞）
    llm_items: list[dict] = []
    adapter = get_llm_adapter()
    if adapter is not None:
        context = f"{company.company_name}（{company.domain or ''}）" if company else None
        llm_items = adapter.extract_signals_v2(db, source_text, source_type, context, "source_record", record.id)
        stats.llm_used = True

    # LLM 条目按类型合并进规则草稿（补充 fields/fact/inference），未命中规则的新类型单独成候选
    llm_by_type: dict[str, dict] = {}
    for item in llm_items:
        stype = str(item.get("signal_type") or "").upper()
        if stype:
            llm_by_type.setdefault(stype, item)

    grade = _source_grade(db, record.source_id)
    resolve_status = record.company_resolve_status or "UNRESOLVED"

    merged_drafts: list[CandidateDraft] = list(drafts)
    for stype, item in llm_by_type.items():
        if not any(d.candidate_type == stype for d in drafts):
            evidence = str(item.get("evidence_text") or "")
            pos = source_text.find(" ".join(evidence.split()[:8]))
            merged_drafts.append(CandidateDraft(
                candidate_type=stype,
                evidence_text=evidence,
                start_offset=max(pos, 0) if pos >= 0 else 0,
                end_offset=(max(pos, 0) + len(evidence)) if pos >= 0 else 0,
                rule_confidence=40,
                extra={"label": stype, "from_llm": True},
            ))

    for draft in merged_drafts:
        llm_item = llm_by_type.get(draft.candidate_type)
        llm_conf: int | None = None
        fact_summary: str | None = None
        inference_summary: str | None = None
        structured: dict = {}
        evidence_text = draft.evidence_text
        if llm_item:
            try:
                llm_conf = max(0, min(int(llm_item.get("confidence", 0)), 100))
            except (TypeError, ValueError):
                llm_conf = None
            fact_summary = (llm_item.get("fact_summary") or None)
            inference_summary = (llm_item.get("inference_summary") or None)
            fields = llm_item.get("fields") or {}
            structured = {
                "who": fields.get("who"), "what": fields.get("what"), "when": fields.get("when"),
                "where": fields.get("where"), "quantity": fields.get("quantity"),
                "object": fields.get("object"), "action": fields.get("action"),
            } if isinstance(fields, dict) else {}
            # LLM 的 evidence_text 若能在原文定位则采用（更精确）
            llm_evidence = str(llm_item.get("evidence_text") or "")
            if llm_evidence and _evidence_in_source(llm_evidence, source_text):
                evidence_text = llm_evidence

        # 3) Evidence 原文校验（不通过 → 不得自动批准）
        evidence_ok = _evidence_in_source(evidence_text, source_text)

        # 4) Confidence（代码计算，非 LLM 输出）
        conf = compute_signal_confidence(
            source_grade=grade,
            evidence_text=evidence_text,
            evidence_in_source=evidence_ok,
            rule_confidence=draft.rule_confidence,
            llm_confidence=llm_conf,
            company_resolve_status=resolve_status,
        )

        # 5) 指纹去重与多来源合并
        fingerprint = _fingerprint_for(record, record.company_id, draft.candidate_type, evidence_text or draft.candidate_type)
        existing = find_duplicate_signal(db, fingerprint)
        if existing is not None:
            merged = merge_evidence(db, existing, source_record_id=record.id, quoted_text=evidence_text or "", start_offset=draft.start_offset, end_offset=draft.end_offset, confidence=conf.score)
            status = "MERGED" if merged else "REJECTED"
            reason = "与既有 Signal 同指纹，多来源合并" if merged else "同来源已有该事件证据"
            candidate = SignalCandidate(
                company_id=record.company_id, source_record_id=record.id,
                candidate_type=draft.candidate_type, evidence_text=(evidence_text or "")[:2000],
                start_offset=draft.start_offset, end_offset=draft.end_offset,
                rule_confidence=draft.rule_confidence, llm_confidence=llm_conf,
                final_confidence=conf.score, status=status, reason=reason,
                structured_json=structured or {}, fact_summary=fact_summary,
                inference_summary=inference_summary, prompt_version=prompts.SIGNAL_EXTRACTOR_V1 if stats.llm_used else None,
                fingerprint=fingerprint, signal_id=existing.id,
            )
            db.add(candidate)
            stats.merged += 1
            continue

        # 6) 落库候选 + 自动批准判定
        auto_ok = (
            evidence_ok
            and conf.score >= settings.signal_auto_approve_threshold
            and grade in {"A", "B"}
            and not draft.extra.get("review_always", False)
        )
        candidate = SignalCandidate(
            company_id=record.company_id, source_record_id=record.id,
            candidate_type=draft.candidate_type, evidence_text=(evidence_text or "")[:2000],
            start_offset=draft.start_offset, end_offset=draft.end_offset,
            rule_confidence=draft.rule_confidence, llm_confidence=llm_conf,
            final_confidence=conf.score,
            status="DETECTED" if auto_ok else "REVIEW_REQUIRED",
            reason=("Evidence 原文可寻且置信度达标" if auto_ok
                    else ("Evidence 未在原文中找到，需人工核对" if not evidence_ok
                          else "置信度或来源等级未达自动批准门槛")),
            structured_json=structured or {}, fact_summary=fact_summary,
            inference_summary=inference_summary,
            prompt_version=prompts.SIGNAL_EXTRACTOR_V1 if stats.llm_used else None,
            fingerprint=fingerprint,
        )
        db.add(candidate)
        db.flush()
        if auto_ok:
            _approve_candidate_into_signal(db, candidate, record, conf.explanation)
            stats.auto_approved += 1
        else:
            stats.review_required += 1
        if not evidence_ok:
            stats.rejected_no_evidence += 1

    # 标记已分析（hash 列表幂等）
    meta = dict(record.metadata_json or {})
    hashes = list(meta.get("signal_analysis_hashes") or [])
    hashes.append(current_hash)
    meta["signal_analysis_hashes"] = hashes[-5:]
    meta["signal_analyzed_at"] = datetime.now(timezone.utc).isoformat()
    record.metadata_json = meta
    db.commit()
    return stats


def run_change_detection(db: Session, new_record: SourceRecord) -> int:
    """版本变化检测：新版本入库后比较相邻旧版本，产出变化类候选。"""
    from app.analyzers.change_detector import detect_changes

    if not new_record.parent_record_id:
        return 0
    old_record = db.get(SourceRecord, new_record.parent_record_id)
    if not old_record:
        return 0
    changes = detect_changes(old_record, new_record)
    created = 0
    for change in changes:
        fingerprint = _fingerprint_for(new_record, new_record.company_id, change.candidate_type, change.evidence_text)
        existing = find_duplicate_signal(db, fingerprint)
        if existing is not None:
            merge_evidence(db, existing, source_record_id=new_record.id, quoted_text=change.evidence_text, start_offset=change.start_offset, end_offset=change.end_offset, confidence=change.rule_confidence)
            continue
        grade = _source_grade(db, new_record.source_id)
        conf = compute_signal_confidence(
            source_grade=grade, evidence_text=change.evidence_text, evidence_in_source=True,
            rule_confidence=change.rule_confidence, llm_confidence=None,
            company_resolve_status=new_record.company_resolve_status or "UNRESOLVED",
        )
        candidate = SignalCandidate(
            company_id=new_record.company_id, source_record_id=new_record.id,
            candidate_type=change.candidate_type, evidence_text=change.evidence_text[:2000],
            start_offset=change.start_offset, end_offset=change.end_offset,
            rule_confidence=change.rule_confidence, llm_confidence=None,
            final_confidence=conf.score, status="REVIEW_REQUIRED",
            reason=f"版本变化检测：{change.change_type} {change.change_value}（来自 v{old_record.version_number}→v{new_record.version_number} 真实比较）",
            structured_json={"change_type": change.change_type, "change_value": change.change_value, **change.extra},
            fact_summary=f"{change.change_type}：{change.change_value}（原文版本对比）",
            fingerprint=fingerprint,
        )
        db.add(candidate)
        created += 1
    if created:
        db.commit()
    return created


def approve_candidate_manually(db: Session, candidate: SignalCandidate, *, note: str | None = None, reject: bool = False) -> Signal | None:
    """人工审核候选：approve → 正式 Signal；reject → REJECTED。写 AuditLog（before/after）。"""
    before = {"status": candidate.status}
    record = db.get(SourceRecord, candidate.source_record_id)
    if reject:
        candidate.status = "REJECTED"
        candidate.reason = (candidate.reason or "") + f" | 人工驳回：{note or '无备注'}"
        write_audit(db, "SIGNAL_CANDIDATE_REJECTED", "signal_candidate", candidate.id, {"before": before, "after": {"status": "REJECTED"}, "note": note})
        db.commit()
        return None
    if record is None:
        raise ValueError("候选关联的 SourceRecord 不存在")
    if not candidate.company_id:
        raise ValueError("候选未关联企业：请先人工关联企业")
    conf = compute_signal_confidence(
        source_grade=_source_grade(db, record.source_id),
        evidence_text=candidate.evidence_text,
        evidence_in_source=_evidence_in_source(candidate.evidence_text, record.raw_text or ""),
        rule_confidence=candidate.rule_confidence,
        llm_confidence=candidate.llm_confidence,
        company_resolve_status=record.company_resolve_status or "UNRESOLVED",
    )
    candidate.final_confidence = conf.score
    signal = _approve_candidate_into_signal(db, candidate, record, conf.explanation)
    write_audit(db, "SIGNAL_CANDIDATE_APPROVED", "signal", signal.id, {"before": before, "after": {"status": "APPROVED"}, "note": note, "candidate_id": candidate.id})
    db.commit()
    return signal
