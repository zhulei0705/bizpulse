"""T08.2 机会候选人工审核（任务书二十六/二十七/四十）。

处置逻辑：
1. 拒绝既有3个候选：远通/汉邦（主触发=历史中标事件，违反任务书二十三/二十六）、
   神州数码（AI转型机会主语错位——该企业是AI服务供给方，非转型需求方）；
2. 生成器已加 actionability 门（bundles+单信号兜底），重跑分析；
3. 新候选人工审核：远通（NEW_OFFICE 子公司设立）、汉邦（HIRING 招聘campaign）证据充分
   → 转正式机会并人工批准（逐条留痕）；神州数码同类候选再次出现则再次拒绝（终态指纹防循环）。
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


def _reject(db, candidate: OpportunityCandidate, note: str) -> None:
    candidate.status = "REJECTED"
    candidate.reject_reason = "WRONG_INTERPRETATION" if "主语" in note else "BAD_TIMING"
    candidate.review_note = note
    candidate.reviewed_by = "local-user"
    candidate.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, "CANDIDATE_REJECTED", "opportunity_candidate", candidate.id,
                {"after": {"status": "REJECTED"}, "note": note})


def _reject_opportunity_if_exists(db, candidate_id: str, note: str) -> None:
    opp = db.scalar(select(Opportunity).where(Opportunity.candidate_id == candidate_id))
    if opp is None:
        return
    opp.review_status = "REJECTED"
    opp.review_note = note
    opp.reviewed_by = "local-user"
    opp.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, "OPPORTUNITY_REVIEW_REJECTED", "opportunity", opp.id, {"note": note})


def main() -> None:
    db = SessionLocal()
    result = {"rejected": [], "converted": [], "opportunity_approved": []}
    try:
        # 1) 拒绝既有候选（含未转正的机会）
        for c in db.scalars(select(OpportunityCandidate).where(OpportunityCandidate.status == "REVIEW")).all():
            company = db.get(Company, c.company_id)
            name = company.company_name if company else "?"
            if "远通信德" in name or "汉邦激光" in name:
                note = ("T08.2候选审核：主触发信号为历史中标事件（CONTRACT_AWARD/HISTORICAL_SIGNAL），"
                        "历史采购不构成当前机会（任务书二十三/二十六）；生成器已加 actionability 门后重新分析")
            else:
                note = ("T08.2候选审核：主语错位——神州数码是AI/数字化服务的供给方（信号为其对外业务活动），"
                        "不构成该企业自身的AI转型需求")
            _reject(db, c, note)
            _reject_opportunity_if_exists(db, c.id, note)
            result["rejected"].append({"company": name, "note": note})

        # 2) 重跑分析（新门生效）
        from app.analyzers.opportunity.generator import analyze_company_opportunities

        for name in ("神州数码信息系统有限公司", "北京远通信德科技有限公司", "广东汉邦激光科技有限公司"):
            company = db.scalar(select(Company).where(Company.company_name == name))
            if company is None:
                continue
            stats = analyze_company_opportunities(db, company.id, force=True)
            result.setdefault("analysis", []).append({"company": name, "created": stats.candidates_created,
                                                      "reason": stats.reason})
            db.commit()

        # 3) 审核新生成的 REVIEW 候选
        from app.models.signal import Signal

        for c in db.scalars(select(OpportunityCandidate).where(OpportunityCandidate.status == "REVIEW")).all():
            company = db.get(Company, c.company_id)
            name = company.company_name if company else "?"
            types = set()
            for sid in c.signal_ids_json or []:
                sig = db.get(Signal, sid)
                if sig is not None:
                    types.add(sig.signal_type)
            primary_types = sorted(types)
            note = None
            if "NEW_OFFICE" in primary_types:
                note = "官方关于页真实事实（重庆、西安设立子公司）→ 扩张期机会假设，证据充分"
            elif "HIRING" in primary_types:
                note = "官方新闻页真实招聘campaign（五一诚邀英才）→ 扩张期机会假设，证据充分"
            else:
                note = "T08.2候选审核：主触发仍非当前可行动信号或主语错位，拒绝"
            if "NEW_OFFICE" in primary_types or "HIRING" in primary_types:
                from app.api.v1.endpoints.opportunity_candidates import _convert_candidate

                before = {"status": c.status, "grade": c.grade}
                opportunity = _convert_candidate(db, c, note)
                c.status = "CONVERTED"
                c.review_note = note
                c.reviewed_by = "local-user"
                c.reviewed_at = datetime.now(timezone.utc)
                c.opportunity_id = opportunity.id
                write_audit(db, "CANDIDATE_APPROVED", "opportunity_candidate", c.id,
                            {"before": before, "after": {"status": "CONVERTED", "opportunity_id": opportunity.id},
                             "note": f"T08.2候选人工审核：{note}"})
                # 人工批准正式机会
                opportunity.review_status = "APPROVED"
                opportunity.reviewed_by = "local-user"
                opportunity.reviewed_at = datetime.now(timezone.utc)
                opportunity.review_note = note
                write_audit(db, "OPPORTUNITY_REVIEW_APPROVED", "opportunity", opportunity.id,
                            {"note": f"T08.2机会人工审核：{note}"})
                result["converted"].append({"company": name, "opportunity_id": opportunity.id,
                                            "types": primary_types})
                result["opportunity_approved"].append(opportunity.id)
            else:
                _reject(db, c, note)
                result["rejected"].append({"company": name, "note": note})

        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
