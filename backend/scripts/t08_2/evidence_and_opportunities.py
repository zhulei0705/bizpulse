"""T08.2 信号证据回填 + 机会分析触发。

1. 对 T08.2 生成的已批准信号回填 SignalEvidence（excerpt 必须是来源原文精确子串）；
2. 对有可行动信号的3家企业触发 analyze_company_opportunities（候选一律人工审核）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.signal import Signal, SignalEvidence  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

ANALYZE_COMPANY_NAMES = ["神州数码信息系统有限公司", "北京远通信德科技有限公司", "广东汉邦激光科技有限公司"]


def backfill_evidence(db) -> dict:
    stats = {"checked": 0, "created": 0, "not_found": []}
    signals = db.scalars(select(Signal).where(Signal.status == "APPROVED")).all()
    for s in signals:
        p = s.payload_json or {}
        if p.get("extractor") not in {"t082_enrichment_v1", "t082_manual_reclass_v1"}:
            continue
        stats["checked"] += 1
        existing = db.scalar(select(SignalEvidence).where(SignalEvidence.signal_id == s.id))
        if existing is not None:
            continue
        record = s.source_record
        raw = (record.raw_text if record else "") or ""
        excerpt = p.get("excerpt") or s.description or ""
        # excerpt 可能是空白规范化后的片段 —— 逐句在原文中定位最长可精确匹配子串
        needle = " ".join(excerpt.split())
        offset = raw.find(needle)
        if offset < 0:
            # 空白差异：去掉所有空白后再定位（仍是原文连续子串）
            compact = "".join(raw.split())
            pos = compact.find("".join(needle.split()))
            if pos >= 0:
                # 映射回原文本的近似 offset
                count = 0
                for i, ch in enumerate(raw):
                    if not ch.isspace():
                        if count == pos:
                            offset = i
                            break
                        count += 1
        if offset < 0:
            stats["not_found"].append(s.id)
            continue
        db.add(SignalEvidence(
            signal_id=s.id, source_record_id=record.id,
            quoted_text=needle, start_offset=offset, end_offset=offset + len(needle),
            evidence_type="ORIGINAL_TEXT", confidence=s.confidence,
            verification_status="VERIFIED",
        ))
        write_audit(db, "T082_SIGNAL_EVIDENCE_BACKFILLED", "signal", s.id,
                    {"source_record_id": record.id, "offset": offset})
        stats["created"] += 1
    return stats


def run_analysis(db) -> list[dict]:
    from app.analyzers.opportunity.generator import analyze_company_opportunities

    results = []
    for name in ANALYZE_COMPANY_NAMES:
        company = db.scalar(select(Company).where(Company.company_name == name))
        if company is None:
            results.append({"company": name, "error": "not_found"})
            continue
        stats = analyze_company_opportunities(db, company.id, force=True)
        results.append({"company": name, "status": stats.status, "reason": stats.reason,
                        "candidates_created": stats.candidates_created,
                        "candidates_updated": stats.candidates_updated,
                        "need_more_evidence": stats.need_more_evidence,
                        "bundles": stats.bundles})
        db.commit()
    return results


def main() -> None:
    db = SessionLocal()
    try:
        ev = backfill_evidence(db)
        analysis = run_analysis(db)
        db.commit()
        result = {"evidence": ev, "analysis": analysis,
                  "ran_at": datetime.now(timezone.utc).isoformat()}
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
