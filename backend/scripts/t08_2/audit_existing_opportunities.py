"""T08.2 存量 Opportunity 重审（任务书二十七）：逐个计算 actionability 并审计留痕，不删除不改阶段。"""
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
from app.services.actionability import opportunity_actionability  # noqa: E402
from app.services.audit import write_audit  # noqa: E402


def main() -> None:
    db = SessionLocal()
    result = []
    try:
        for opp in db.scalars(select(Opportunity).where(Opportunity.status == "ACTIVE")).all():
            company = db.get(Company, opp.company_id)
            a = opportunity_actionability(db, opp)
            note = {
                "opportunity_id": opp.id,
                "company": company.company_name if company else None,
                "title": opp.title,
                "stage": opp.stage,
                "review_status": opp.review_status,
                "primary_signal_id": opp.primary_signal_id,
                "actionability": a,
                "decision": "保留现状（stage/review_status 不变）；actionability 如实记录",
                "audit_version": "T08.2",
            }
            write_audit(db, "T082_OPPORTUNITY_ACTIONABILITY_AUDIT", "opportunity", opp.id, note)
            result.append(note)
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"audited": len(result)}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
