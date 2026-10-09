"""T08.1：T06 Experiment 审计 + OUTREACH 历史记录标注 + 真实主体 organization_type 修正。

原则：
- Experiment：只审计不修改（KEEP/PAUSE/COMPLETE/MANUAL_FIX_REQUIRED 为建议，禁止自动篡改历史实验定义）；
- OUTREACH：contact_id=null 的历史发送记录保留事实，只在 audit_logs 标注 LEGACY_UNVERIFIED_CONTACT，
  不伪造 Contact 补链；
- organization_type 修正仅限名称规则可判定的真实主体（大学/研究所），并在审计中留痕。
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
from app.models.experiment import Experiment, ExperimentTarget, Interaction  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

OUT_PATH = ROOT / "_t08_out.txt"

UNIVERSITY_MARKERS = ("大学", "学院")
RESEARCH_MARKERS = ("研究院", "研究所", "科学院")


def audit_experiment(db) -> dict:
    exp = db.scalar(select(Experiment).where(Experiment.name == "华南理工科研仪器采购验证"))
    if exp is None:
        return {"found": False}
    targets = db.scalars(select(ExperimentTarget).where(ExperimentTarget.experiment_id == exp.id)).all()
    interactions = db.scalars(select(Interaction).where(Interaction.experiment_id == exp.id)).all()

    criteria_text = exp.success_criteria or ""
    # 一致性检查：success_criteria 提到的企业数 vs target_company_count
    criteria_count_consistent = True
    note = ""
    if "3 家" in criteria_text and (exp.target_company_count or 0) != 3:
        criteria_count_consistent = False
        note = f"success_criteria 文本提及“3 家目标企业”，但 target_company_count={exp.target_company_count}（单企业联调验证实验，定义文本不一致；不自动修改历史定义）"

    # 判断：这是 T06 联调/单企业验证实验（1 家目标、1 个真实 OUTREACH 互动、无 outcome 记录）
    recommendation = "KEEP"
    audit_payload = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": exp.id,
        "status": exp.status,
        "target_company_count": exp.target_company_count,
        "target_contacts": exp.target_contacts,
        "success_criteria": criteria_text,
        "actual_targets": len(targets),
        "actual_interactions": len(interactions),
        "criteria_count_consistent": criteria_count_consistent,
        "judgement": "T06 联调/单企业验证实验（1 家目标 + 1 条真实 OUTREACH）",
        "recommendation": recommendation,
        "note": note,
        "action_taken": "未修改任何实验定义字段（仅记录审计）",
    }
    write_audit(db, "T08_EXPERIMENT_AUDITED", "experiment", exp.id, audit_payload)
    return {"found": True, **audit_payload}


def mark_legacy_outreach(db) -> dict:
    """contact_id=null 的历史 OUTREACH：保留事实，audit 标注 LEGACY_UNVERIFIED_CONTACT。"""
    rows = db.scalars(select(Interaction).where(
        Interaction.interaction_type == "OUTREACH",
        Interaction.contact_id.is_(None),
    )).all()
    marked = []
    for it in rows:
        write_audit(db, "LEGACY_UNVERIFIED_CONTACT", "interaction", it.id, {
            "marked_at": datetime.now(timezone.utc).isoformat(),
            "interaction_type": it.interaction_type,
            "channel": it.channel,
            "contact_id": it.contact_id,
            "company_id": it.company_id,
            "occurred_at": str(it.occurred_at),
            "note": "真实发生过的人工发送；发送对象无法通过现有 SourceRecord 关联到具体 Contact，verification_status=UNVERIFIED，禁止伪造 Contact 补链",
        })
        marked.append(it.id)
    return {"outreach_total": len(rows), "marked": marked}


def fix_organization_types(db) -> list[dict]:
    """修正真实主体的 organization_type / verification_status。

    范围（两条路径）：
    - verification_status != UNVERIFIED 且 organization_type=UNKNOWN：仅按名称规则修类型；
    - verification_status = UNVERIFIED 但存在 A 级来源记录（如 ccgp 公告）的真实主体：
      PUBLIC_SOURCE_VERIFIED + 名称规则类型（与其它公告发现主体一致）。
    无任何来源记录的主体（如历史遗留 haidilao/BYD）一律不动，仅报告。
    """
    changed = []

    def _rule_type(name: str) -> str | None:
        if any(k in name for k in RESEARCH_MARKERS):
            return "RESEARCH_INSTITUTE"
        if any(k in name for k in UNIVERSITY_MARKERS):
            return "UNIVERSITY"
        return None

    def _apply(c: Company, old_verification: str, reason: str) -> None:
        new_type = _rule_type(c.company_name)
        updates = {}
        if new_type and c.organization_type != new_type:
            updates["organization_type"] = {"before": c.organization_type, "after": new_type}
            c.organization_type = new_type
        if old_verification == "UNVERIFIED" and c.verification_status == "UNVERIFIED":
            updates["verification_status"] = {"before": "UNVERIFIED", "after": "PUBLIC_SOURCE_VERIFIED"}
            c.verification_status = "PUBLIC_SOURCE_VERIFIED"
            from datetime import datetime as _dt, timezone as _tz
            c.verified_at = _dt.now(_tz.utc)
        if updates:
            write_audit(db, "T08_ORG_TYPE_FIXED", "company", c.id, {
                "company_name": c.company_name, "updates": updates, "basis": reason,
            })
            changed.append({"company_id": c.id, "company_name": c.company_name, **updates})

    # 路径1：已验证但类型 UNKNOWN
    for c in db.scalars(select(Company).where(
        Company.organization_type == "UNKNOWN",
        Company.verification_status != "UNVERIFIED",
    )).all():
        _apply(c, c.verification_status, "名称规则判定（大学/研究院所关键词）+ 已有真实来源验证")
    # 路径2：未验证但存在真实来源记录的主体
    for c in db.scalars(select(Company).where(
        Company.organization_type == "UNKNOWN",
        Company.verification_status == "UNVERIFIED",
    )).all():
        has_real_source = False
        for rec in c.source_records:
            src = rec.source
            if src is not None and (src.reliability_grade or "").upper() == "A":
                has_real_source = True
                break
        if has_real_source:
            _apply(c, "UNVERIFIED", "存在 A 级官方来源记录（ccgp 公告）→ PUBLIC_SOURCE_VERIFIED + 名称规则类型")
    return changed


def main() -> None:
    db = SessionLocal()
    try:
        exp_audit = audit_experiment(db)
        outreach = mark_legacy_outreach(db)
        org_fixed = fix_organization_types(db)
        db.commit()
        result = {"experiment_audit": exp_audit, "outreach": outreach, "org_type_fixed": org_fixed}
        OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
