"""T08.2 第二轮信号人工审核（规则收窄后）。

- 汉邦激光 HIRING："五一职等你来！汉邦激光诚邀英才" → APPROVE（真实招聘 campaign，官方新闻页）；
- 比亚迪 HIRING："诚邀所有品牌车主进店体验" → REJECT（营销文案误匹配，'诚邀'规则已收窄为'诚邀英才'）；
- 远通信德 NEW_OFFICE："在重庆和西安设立子公司" → APPROVE（官方关于页真实事实，人工复审归类）。
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
from app.services.audit import write_audit  # noqa: E402


def main() -> None:
    db = SessionLocal()
    result = {"approved": 0, "rejected": 0, "details": []}
    try:
        signals = db.scalars(select(Signal).where(Signal.status == "VALID")).all()
        for s in signals:
            p = s.payload_json or {}
            if p.get("extractor") not in {"t082_enrichment_v1", "t082_manual_reclass_v1"}:
                continue
            excerpt = s.description or ""
            before = {"status": s.status}
            if s.signal_type == "HIRING" and "诚邀英才" in excerpt and "职等你来" in excerpt:
                s.status = "APPROVED"
                s.verification_status = "VERIFIED"
                s.last_verified_at = datetime.now(timezone.utc)
                write_audit(db, "SIGNAL_APPROVED", "signal", s.id, {
                    "before": before, "after": {"status": "APPROVED"},
                    "note": "T08.2第二轮人工审核：官方新闻页真实招聘campaign（五一诚邀英才），证据完整"})
                result["approved"] += 1
                result["details"].append({"id": s.id, "action": "APPROVED", "type": s.signal_type})
            elif s.signal_type == "NEW_OFFICE" and "设立子公司" in excerpt:
                s.status = "APPROVED"
                s.verification_status = "VERIFIED"
                s.last_verified_at = datetime.now(timezone.utc)
                write_audit(db, "SIGNAL_APPROVED", "signal", s.id, {
                    "before": before, "after": {"status": "APPROVED"},
                    "note": "T08.2第二轮人工审核：官方关于页真实事实（重庆、西安设子公司），证据完整"})
                result["approved"] += 1
                result["details"].append({"id": s.id, "action": "APPROVED", "type": s.signal_type})
            elif s.signal_type == "HIRING" and "车主" in excerpt:
                s.status = "REJECTED"
                write_audit(db, "SIGNAL_REJECTED", "signal", s.id, {
                    "before": before, "after": {"status": "REJECTED"},
                    "note": "T08.2第二轮人工审核：营销文案误匹配（'诚邀车主进店体验'非招聘），HIRING规则已收窄为'诚邀英才'"})
                result["rejected"] += 1
                result["details"].append({"id": s.id, "action": "REJECTED", "type": s.signal_type})
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"approved": result["approved"], "rejected": result["rejected"]}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
