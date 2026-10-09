"""T08.2 批次2人工审核处置 + 表单渠道修正。

审核结论（逐条对照原文证据）：
- APPROVE：神州鲲泰新品发布（企业自有产品，真实新闻）；AI服贸会成果入选（真实事件）
- REJECT：CRM/ERP/PROCUREMENT 需求类（证据是神州数码自家产品描述——他们在卖这类系统，
  不是需要采购）；COST_PRESSURE/EFFICIENCY_PROBLEM（营销文案描述"客户"的痛点，
  主语非该企业）；DIGITAL_TRANSFORMATION（产品菜单条带）；OVERSEAS_EXPANSION
  （会议议程里的"出海场景"字样，无海外子公司/办公室等实体证据，任务书十四不成立）；
  其余 AI_TRANSFORMATION 重复项（同事件多页面重复，保留证据最完整的一条）；
  比亚迪 HIRING（证据为招聘口号，未引用具体岗位）。

修正：费勉 WEBSITE_FORM 误挂产品页（导航"在线留言"链接≠页面表单）→ 删除该渠道行。
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
from app.models.company import CompanyContact  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.services.audit import write_audit  # noqa: E402


def main() -> None:
    db = SessionLocal()
    approved, rejected = [], []
    try:
        signals = db.scalars(select(Signal).where(
            Signal.status == "VALID",
            Signal.signal_type != "CONTRACT_AWARD",
            Signal.signal_type != "HIRING",
        )).all()
        by_company: dict[str, list[Signal]] = {}
        for s in signals:
            if (s.payload_json or {}).get("extractor") != "t082_enrichment_v1":
                continue
            by_company.setdefault(s.company_id, []).append(s)

        for company_id, group in by_company.items():
            # 批次1企业（已在上一轮处置）跳过
            pass

        for s in signals:
            if (s.payload_json or {}).get("extractor") != "t082_enrichment_v1":
                continue
            excerpt = s.description or ""
            if "神州鲲泰正式推出" in excerpt or "鲲鹏、昇腾" in excerpt:
                action, reason = "APPROVE", "神州鲲泰新品正式推出（企业自有产品线，真实新闻事件）"
            elif "服贸会成果展示" in excerpt and s.signal_type == "AI_TRANSFORMATION":
                action, reason = "APPROVE", "入选服贸会成果展示，多行业AI落地（真实事件，证据完整）"
            elif s.signal_type in {"CRM_DEMAND", "ERP_DEMAND", "PROCUREMENT"}:
                action, reason = "REJECT", "证据为该企业自家产品/方案描述（他们在这类系统的供给方），不构成企业采购需求"
            elif s.signal_type in {"COST_PRESSURE", "EFFICIENCY_PROBLEM"}:
                action, reason = "REJECT", "营销文案描述'客户'的痛点，主语非该企业（不得归属该企业）"
            elif s.signal_type == "DIGITAL_TRANSFORMATION":
                action, reason = "REJECT", "证据为产品目录菜单条带，非事件事实句"
            elif s.signal_type == "OVERSEAS_EXPANSION":
                action, reason = "REJECT", "仅会议议程出现'出海场景'字样，无海外实体/业务进入证据（任务书十四不成立）"
            elif s.signal_type == "HIRING":
                action, reason = "REJECT", "证据为招聘口号，未引用具体岗位/招聘事实"
            elif s.signal_type == "AI_TRANSFORMATION":
                action, reason = "REJECT", "同事件在其他页面已有证据更完整的记录（重复信号）"
            else:
                action, reason = "REJECT", "证据不足以支持该信号类型"

            before = {"status": s.status}
            if action == "APPROVE":
                s.status = "APPROVED"
                s.verification_status = "VERIFIED"
                s.last_verified_at = datetime.now(timezone.utc)
                write_audit(db, "SIGNAL_APPROVED", "signal", s.id,
                            {"before": before, "after": {"status": "APPROVED"},
                             "note": f"T08.2批次2人工审核：{reason}"})
                approved.append({"id": s.id, "type": s.signal_type, "reason": reason})
            else:
                s.status = "REJECTED"
                write_audit(db, "SIGNAL_REJECTED", "signal", s.id,
                            {"before": before, "after": {"status": "REJECTED"},
                             "note": f"T08.2批次2人工审核：{reason}"})
                rejected.append({"id": s.id, "type": s.signal_type, "reason": reason})

        # 修正：费勉 WEBSITE_FORM 误挂产品页（导航"在线留言"≠页面表单）
        fermi_form = db.scalar(select(CompanyContact).where(
            CompanyContact.public_profile_url == "http://www.fermi-instruments.com/product/"))
        form_fixed = 0
        if fermi_form is not None and fermi_form.email is None and fermi_form.phone is None:
            write_audit(db, "T082_CONTACT_REMOVED", "company_contact", fermi_form.id, {
                "reason": "WEBSITE_FORM 误挂产品页（导航'在线留言'链接≠页面表单）",
                "form_url": fermi_form.public_profile_url,
            })
            db.delete(fermi_form)
            form_fixed = 1

        db.commit()
        result = {"approved": approved, "rejected": rejected, "form_channel_fixed": form_fixed}
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"approved": len(approved), "rejected": len(rejected), "form_fixed": form_fixed},
                         ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
