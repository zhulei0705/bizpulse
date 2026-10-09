"""T08.1 审批执行：按规则门控对审计通过的 CONTRACT_AWARD 信号执行审批。

前置条件（任务书十一/十三）：
- 阶段A审计完成（payload.t08_audit 存在）；
- 阶段B 10条人工抽查通过（docs/reports/T08.1_signal_spot_check.json verdict == PASS）。

规则门控（全部满足才 APPROVE，否则保持原状态人工审核）：
- recommended_review_action == APPROVE
- subject_role == SUPPLIER（采购方与中标方不能混）
- evidence_quality == PASS（原文精确子串证据存在）
- 来源等级 A 且 URL 为 ccgp.gov.cn（A级官方来源）
- procurement_status == AWARDED（事件语义明确）

审批动作复用现有 /signals/{id}/approve 语义：status=APPROVED、
verification_status=VERIFIED、last_verified_at=now，并写 SIGNAL_APPROVED 审计。
禁止绕过门控批量放行；任何一条不满足 → 保持 VALID 待人工。
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

SPOT_CHECK_REPORT = ROOT / "docs" / "reports" / "T08.1_signal_spot_check.json"


def _gate(audit: dict) -> tuple[bool, str]:
    if audit.get("recommended_review_action") != "APPROVE":
        return False, f"recommended={audit.get('recommended_review_action')}"
    if audit.get("subject_role") != "SUPPLIER":
        return False, f"subject_role={audit.get('subject_role')}"
    if audit.get("evidence_quality") != "PASS":
        return False, "evidence_quality=FAIL"
    if (audit.get("source_grade") or "").upper() != "A":
        return False, f"source_grade={audit.get('source_grade')}"
    if "ccgp.gov.cn" not in (audit.get("source_url") or "").lower():
        return False, "source_url not ccgp.gov.cn"
    if audit.get("procurement_status") != "AWARDED":
        return False, f"procurement_status={audit.get('procurement_status')}"
    return True, "all conditions met"


def main() -> None:
    if not SPOT_CHECK_REPORT.exists():
        raise SystemExit("缺少阶段B抽查报告，先运行 spot_check_signals.py")
    spot = json.loads(SPOT_CHECK_REPORT.read_text(encoding="utf-8"))
    if spot.get("summary", {}).get("verdict") != "PASS":
        raise SystemExit(f"阶段B抽查未通过（verdict={spot['summary'].get('verdict')}），禁止审批")

    db = SessionLocal()
    approved, kept, rejected = 0, 0, 0
    try:
        signals = db.scalars(select(Signal).where(
            Signal.signal_type == "CONTRACT_AWARD",
            Signal.status.in_(["VALID", "REVIEW"]),
        )).all()
        for signal in signals:
            audit = (signal.payload_json or {}).get("t08_audit") or {}
            ok, reason = _gate(audit)
            if not ok:
                kept += 1
                write_audit(db, "T08_SIGNAL_REVIEW_HELD", "signal", signal.id,
                            {"reason": reason, "kept_status": signal.status})
                continue
            before = {"status": signal.status, "verification_status": signal.verification_status}
            signal.status = "APPROVED"
            signal.verification_status = "VERIFIED"
            signal.last_verified_at = datetime.now(timezone.utc)
            write_audit(db, "SIGNAL_APPROVED", "signal", signal.id, {
                "before": before,
                "after": {"status": "APPROVED"},
                "note": "T08.1 规则门控审批：A级ccgp来源+主体SUPPLIER匹配+Evidence原文精确子串+AWARDED语义（阶段B 10条抽查通过）",
            })
            approved += 1
        db.commit()
    finally:
        db.close()

    summary = {"total_signals": approved + kept, "approved": approved, "kept_for_manual": kept, "rejected": rejected}
    (ROOT / "_t08_out.txt").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
