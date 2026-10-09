"""证据版本门：偏移只表示 SourceRecord.raw_text 的 Unicode 字符索引。

legacy raw_text 是已存正文，Crawl4AI raw_text 是 CLEANED_DOM_TEXT；HTML/原始
可见文本另存快照，不能借用其偏移。content_hash 为采集去重指纹，body_sha256
才是引用文本哈希。无可信原版本时隔离，不改写原文。
"""
from hashlib import sha256
from pathlib import Path
from app.core.config import BASE_DIR

BLOCKED = {'INVALID_EVIDENCE', 'MISSING_SOURCE_SNAPSHOT', 'QUARANTINED'}

def text_contract(record):
    return {'basis': (record.metadata_json or {}).get('text_basis', 'STORED_TEXT'),
            'text_version': record.version_number, 'offset_unit': 'UNICODE_CHARACTER',
            'body_sha256': sha256((record.raw_text or '').encode('utf-8')).hexdigest()}

def exact_reference(text, excerpt, start, end):
    return bool(excerpt and isinstance(start, int) and isinstance(end, int)
                and 0 <= start < end <= len(text or '') and text[start:end] == excerpt)

def locate_exact(text, excerpt):
    """只定位未经改写的完整引用；空值/非原文返回未知，绝不归一化正文。"""
    if not excerpt:return None
    start = (text or '').find(excerpt)
    return (start, start + len(excerpt)) if start >= 0 else None

def record_issues(record):
    if record is None:return ['MISSING_SOURCE_RECORD']
    meta = record.metadata_json or {}
    state = meta.get('evidence_integrity') or {}
    reasons = list(state.get('reasons') or []) if state.get('status') in BLOCKED else []
    if record.verification_status in BLOCKED:reasons.append(record.verification_status)
    path = record.raw_html_path
    if path:
        target = (BASE_DIR / path).resolve()
        if not target.is_relative_to(BASE_DIR.resolve()) or not target.is_file():
            reasons.append('MISSING_SOURCE_SNAPSHOT')
    contract = meta.get('evidence_text_contract')
    if contract and contract != text_contract(record):reasons.append('TEXT_VERSION_OR_HASH_MISMATCH')
    return sorted(set(reasons))

def evidence_issues(db, evidence):
    from app.models.source import SourceRecord
    record = db.get(SourceRecord, evidence.source_record_id)
    issues = record_issues(record)
    if evidence.verification_status in BLOCKED:issues.append(evidence.verification_status)
    if record and not exact_reference(record.raw_text or '', evidence.quoted_text,
                                     evidence.start_offset, evidence.end_offset):issues.append('INVALID_EVIDENCE')
    return sorted(set(issues))

def signal_issues(db, signal):
    from app.models.source import SourceRecord
    from app.models.signal import SignalEvidence
    from sqlalchemy import select
    state = (signal.payload_json or {}).get('evidence_integrity') or {}
    issues = list(state.get('reasons') or []) if state.get('status') in BLOCKED else []
    issues += record_issues(db.get(SourceRecord, signal.source_record_id))
    for e in db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == signal.id)):
        issues += evidence_issues(db, e)
    return sorted(set(issues))

def opportunity_issues(db, opportunity):
    from app.models.signal import Signal
    from app.models.source import SourceRecord
    issues=[]
    if 'INVALID_EVIDENCE_REVIEW_REQUIRED' in (opportunity.risk_notes or []):issues.append('INVALID_EVIDENCE')
    ids={opportunity.primary_signal_id} if opportunity.primary_signal_id else set()
    for e in opportunity.evidences:
        if e.source_record_id:issues+=record_issues(db.get(SourceRecord,e.source_record_id))
        if e.signal_id:ids.add(e.signal_id)
    for sid in ids:
        signal=db.get(Signal,sid)
        issues+=signal_issues(db,signal) if signal else ['MISSING_SIGNAL']
    return sorted(set(issues))
