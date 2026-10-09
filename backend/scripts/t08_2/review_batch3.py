"""T08.2 批次3人工审核处置。

- 远通信德 DIGITAL_TRANSFORMATION ×2：
  · "国际通道数字化转型服务商" → REJECT（企业定位标语，非事件）；
  · "在重庆和西安设立子公司" → 证据真实但规则归类型错误：按任务书十三/原文事实
    人工复审为 NEW_OFFICE（新设分支机构），旧信号 REJECT，新信号 VALID 待审；
- 比亚迪 HIRING（招聘口号）→ REJECT。
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
from app.models.signal import Signal  # noqa: E402
from app.services.actionability import record_signal_actionability  # noqa: E402
from app.services.audit import write_audit  # noqa: E402


def main() -> None:
    db = SessionLocal()
    result = {"rejected": 0, "reclassified": 0}
    try:
        signals = db.scalars(select(Signal).where(
            Signal.status == "VALID",
            (Signal.payload_json.cast(None).like('%"t082_enrichment_v1"%')) if False else Signal.signal_type.isnot(None),
        )).all()
        for s in signals:
            if (s.payload_json or {}).get("extractor") != "t082_enrichment_v1":
                continue
            excerpt = s.description or ""
            if "设立子公司" in excerpt and "重庆和西安" in excerpt:
                # 人工复审：证据真实，按原文事实重新归类为 NEW_OFFICE
                before = {"status": s.status, "signal_type": s.signal_type}
                s.status = "REJECTED"
                write_audit(db, "SIGNAL_REJECTED", "signal", s.id, {
                    "before": before, "after": {"status": "REJECTED"},
                    "note": "T08.2批次3人工复审：类型归属错误（该证据的事件事实是设立子公司，不是数字化转型），按原文重新归类生成 NEW_OFFICE",
                })
                new_signal = Signal(
                    company_id=s.company_id, source_record_id=s.source_record_id,
                    signal_type="NEW_OFFICE",
                    title=f"新设分支机构：{excerpt[:80]}",
                    description=excerpt,
                    published_at=s.published_at, collected_at=datetime.now(timezone.utc),
                    confidence=72, reliability_score=s.reliability_score,
                    status="VALID", fact_or_inference="FACT",
                    payload_json={"extractor": "t082_manual_reclass_v1",
                                  "page_type": (s.payload_json or {}).get("page_type"),
                                  "excerpt": excerpt,
                                  "reclassified_from": s.signal_type},
                )
                db.add(new_signal)
                db.flush()
                record_signal_actionability(db, new_signal)
                write_audit(db, "SIGNAL_CREATED_MANUAL_RECLASS", "signal", new_signal.id, {
                    "from_signal": s.id, "signal_type": "NEW_OFFICE",
                    "note": "原文事实：公司在重庆和西安设立子公司（真实事件，规则归类型错误，人工复审改归类）",
                })
                result["reclassified"] += 1
            elif "数字化转型服务商" in excerpt or s.signal_type == "DIGITAL_TRANSFORMATION":
                before = {"status": s.status}
                s.status = "REJECTED"
                write_audit(db, "SIGNAL_REJECTED", "signal", s.id, {
                    "before": before, "after": {"status": "REJECTED"},
                    "note": "T08.2批次3人工审核：企业定位标语（'数字化转型服务商'是其业务定位），非转型事件",
                })
                result["rejected"] += 1
            elif s.signal_type == "HIRING":
                before = {"status": s.status}
                s.status = "REJECTED"
                write_audit(db, "SIGNAL_REJECTED", "signal", s.id, {
                    "before": before, "after": {"status": "REJECTED"},
                    "note": "T08.2批次3人工审核：证据为招聘口号，未引用具体岗位/招聘事实",
                })
                result["rejected"] += 1
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
