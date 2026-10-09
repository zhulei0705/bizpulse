"""T08.2 批次1人工审核处置 + 修复后重新分析。

批次1质检发现（任务书三十八：Signal严重误判 → 暂停并修解析器）：
- 5条 HIRING：证据为站点导航菜单条带（"诚聘英才"来自导航）→ REJECT
- 1条 FUNDING：发展历程页时间线（完成C轮融资为历史沿革）→ REJECT
- 1条 HIRING：证据为岗位JD职责句（与招聘事件无亲和）→ REJECT
- 1条 PROCUREMENT：岗位JD"管理外购件采购周期"≠采购需求 → REJECT

处置：REJECT（保留审计留痕），然后用修复后的引擎对已采集 t082 页面重新生成信号
（新信号仍 VALID 待人工审核）。
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
from app.models.signal import Signal  # noqa: E402
from app.models.source import SourceRecord  # noqa: E402
from app.services.audit import write_audit  # noqa: E402
from app.services.enrichment_runner import _signals_from_record  # noqa: E402

# 批次1审核拒绝清单（signal_id → 理由）
REJECTS = {
    "nav_hiring": "证据为站点导航菜单条带（'诚聘英才'来自导航），非实质招聘事实",
    "timeline_funding": "发展历程页时间线事件（历史沿革），非近期融资事件",
    "jd_hiring": "证据为岗位JD职责句，与招聘事件无直接亲和",
    "jd_procurement": "岗位JD'管理外购件采购周期'是职责描述，不是企业采购需求",
}


def review_batch1(db) -> int:
    """拒绝全部 t082 生成的 VALID 信号（批次1全部为噪音）。"""
    rejected = 0
    signals = db.scalars(select(Signal).where(
        Signal.status == "VALID",
        Signal.signal_type != "CONTRACT_AWARD",
    )).all()
    for s in signals:
        payload = s.payload_json or {}
        if payload.get("extractor") not in {"t082_enrichment_v1"}:
            continue
        page_type = payload.get("page_type") or ""
        if "融资" in (s.description or "") and "完成" in (s.description or ""):
            reason = REJECTS["timeline_funding"]
        elif "采购" in (s.description or ""):
            reason = REJECTS["jd_procurement"]
        elif "任职" in (s.description or "") or "负责" in (s.description or ""):
            reason = REJECTS["jd_hiring"]
        else:
            reason = REJECTS["nav_hiring"]
        before = {"status": s.status}
        s.status = "REJECTED"
        write_audit(db, "SIGNAL_REJECTED", "signal", s.id, {
            "before": before, "after": {"status": "REJECTED"},
            "note": f"T08.2批次1人工审核：{reason}",
            "page_type": page_type, "excerpt": (s.description or "")[:120],
        })
        rejected += 1
    return rejected


def regen_signals(db) -> int:
    """用修复后的引擎对已采集 t082 页面重新生成信号（带去重）。"""
    created = 0
    records = db.scalars(select(SourceRecord).where(
        SourceRecord.metadata_json.like('%"t082_enrichment"%'))).all()
    for record in records:
        company = db.get(Company, record.company_id) if record.company_id else None
        if company is None:
            continue
        page_type = (record.metadata_json or {}).get("page_type") or "OTHER"
        signals = _signals_from_record(db, company, record, page_type)
        created += len(signals)
    return created


def main() -> None:
    db = SessionLocal()
    try:
        rejected = review_batch1(db)
        created = regen_signals(db)
        db.commit()
        result = {"rejected": rejected, "regenerated": created,
                  "ran_at": datetime.now(timezone.utc).isoformat()}
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
