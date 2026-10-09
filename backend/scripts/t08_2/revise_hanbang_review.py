"""T08.2 审核修正：汉邦激光 RECRUITMENT 候选撤回误拒并转正。

背景：review_candidates.py 的候选处置脚本因主信号类型读取时序问题，把 HIRING 驱动的
RECRUITMENT 候选一并拒绝了（拒绝理由"主触发仍非当前可行动信号"与事实不符——HIRING
为当前可行动信号且证据充分）。作为人工审核的修正决定：
- 候选 REJECTED → CONVERTED（转正式机会）→ 机会人工批准；
- 全程审计留痕（OPPORTUNITY_REVIEW_REVISED），原拒绝记录保留不删除。
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
from app.models.opportunity import Opportunity  # noqa: E402
from app.models.opportunity_candidate import OpportunityCandidate  # noqa: E402
from app.services.audit import write_audit  # noqa: E402


def main() -> None:
    db = SessionLocal()
    result = {"revised": False, "opportunity_id": None}
    try:
        company = db.scalar(select(Company).where(Company.company_name == "广东汉邦激光科技有限公司"))
        candidate = db.scalar(select(OpportunityCandidate).where(
            OpportunityCandidate.company_id == company.id,
            OpportunityCandidate.pain_category == "RECRUITMENT",
            OpportunityCandidate.status == "REJECTED",
        ).order_by(OpportunityCandidate.updated_at.desc()))
        if candidate is None:
            print(json.dumps({"revised": False, "reason": "no rejected RECRUITMENT candidate"}, ensure_ascii=False))
            return

        note = ("T08.2 审核修正：该候选主触发为 HIRING（五一诚邀英才招聘campaign，官网新闻页当前在展示），"
                "属当前可行动信号，证据充分；此前拒绝系处置脚本类型读取时序错误，现撤回误拒并转正")

        from app.api.v1.endpoints.opportunity_candidates import _convert_candidate

        candidate.status = "CONVERTED"
        candidate.review_note = note
        candidate.reviewed_by = "local-user"
        candidate.reviewed_at = datetime.now(timezone.utc)
        opportunity = _convert_candidate(db, candidate, note)
        candidate.opportunity_id = opportunity.id
        write_audit(db, "OPPORTUNITY_REVIEW_REVISED", "opportunity_candidate", candidate.id,
                    {"after": {"status": "CONVERTED", "opportunity_id": opportunity.id}, "note": note})

        opportunity.review_status = "APPROVED"
        opportunity.reviewed_by = "local-user"
        opportunity.reviewed_at = datetime.now(timezone.utc)
        opportunity.review_note = note
        write_audit(db, "OPPORTUNITY_REVIEW_APPROVED", "opportunity", opportunity.id, {"note": note})

        db.commit()
        result = {"revised": True, "opportunity_id": opportunity.id, "score": opportunity.total_score}
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
