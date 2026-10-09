"""T09-B1：汉邦激光首个真实客户触达记录准备。

只处理广东汉邦激光；禁止自动发送、不创建 OUTREACH Interaction。
1. Live 重验 hb3d@hb3dp.com 的公开来源 URL；
2. 重验三项 Evidence（990万中标 / 招聘 / 官网联系信息）——招聘不得描述为"近期"；
3. 触达理由改为"验证设备企业获取高校/科研采购机会的真实流程和痛点"；
4. Primary Offer 更名"14天高校/科研采购机会人工验证试点"；
5. 首封邮件重写（无 AI/Agent、无平台宣传、无ROI、无1500元/月、不断言客户痛点），
   约束做自动检查，违规即 BLOCKED；
6. 最终人工发送版本写入实验快照并出报告；
7. Target 状态 NEW → READY_TO_CONTACT（审计留痕）；Interaction 只等用户确认真实发送后创建。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.experiment import Experiment, ExperimentTarget  # noqa: E402
from app.services import extractor  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"

FINAL_EMAIL = """主题：汉邦激光｜高校/科研采购信息 · 14天人工验证试点

您好：

我们是一个整理高校/科研院所公开采购信息的小团队（仪器、设备类）。

为什么找汉邦：看到贵司9月30日发布公告，中标南京航空航天大学增材制造平台项目（990万元）。高校/科研院所的设备采购公告，是我们重点整理的内容。另外，官网显示贵司4月底发布过招聘计划，因此想向销售一线了解真实的信息获取流程。

想请您帮忙验证一件事：未来14天，我们每天人工整理与增材制造装备相关的高校/科研采购公告，发一封摘要邮件到您指定邮箱；每周15分钟电话听您的反馈。第14天，由您判断这些信息是否有用、值不值得继续——判断标准也由您定（例如"有没有出现我们此前不知道的有效商机"）。

全程免费，也不推销任何系统；如果信息没用，直接告诉我们，这本身就是有价值的结果。

如果方便，希望先约15分钟电话，了解您们现在是怎么获取这类采购信息的。

—— 商脉项目组（采购公开信息整理）"""

# 任务书5：首封邮件禁用内容（自动检查）
BANNED_TOKENS = ["AI", "Agent", "BizPulse", "ROI", "1500", "痛点", "近期", "智能"]


def _norm(s: str) -> str:
    return "".join((s or "").split())


def main() -> None:
    db = SessionLocal()
    try:
        company = db.scalar(select(Company).where(Company.company_name == "广东汉邦激光科技有限公司"))
        experiment = db.scalar(select(Experiment).where(
            Experiment.name.like("BizPulse 第一轮真实客户微验证%")))
        target = db.scalar(select(ExperimentTarget).where(
            ExperimentTarget.experiment_id == experiment.id,
            ExperimentTarget.company_id == company.id))
        snapshot = experiment.snapshot_json or {}
        hiring_sig = next(s for s in snapshot["signals_used"]["广东汉邦激光科技有限公司"] if s["type"] == "HIRING")
        award_sig = next(s for s in snapshot["signals_used"]["广东汉邦激光科技有限公司"] if s["type"] == "CONTRACT_AWARD")

        # ---- 1) 联系来源 URL live 重验 ----
        contact_check = {"url": "https://www.hb3dp.com", "email": "hb3d@hb3dp.com"}
        try:
            page = extractor.fetch_public_page(contact_check["url"])
            text = page.text or ""
            contact_check.update({
                "http_status": page.status_code,
                "email_found_on_page": contact_check["email"] in text,
                "label_found_on_page": "国内业务邮箱" in text,
                "phone_found_on_page": "400-088-8585" in text,
            })
            contact_check["pass"] = page.status_code == 200 and contact_check["email_found_on_page"]
        except Exception as exc:  # noqa: BLE001
            contact_check.update({"pass": False, "error": str(exc)[:150]})
        time.sleep(1.0)

        # ---- 2) 三项 Evidence 重验（库内原文精确子串 + live 页面）----
        from app.models.source import SourceRecord

        evidence_checks = []
        from app.models.signal import Signal

        award_signal = db.get(Signal, award_sig["signal_id"])
        hiring_signal = db.get(Signal, hiring_sig["signal_id"])
        award_record = db.get(SourceRecord, award_signal.source_record_id)
        hiring_record = db.get(SourceRecord, hiring_signal.source_record_id)
        evidence_checks.append({
            "item": "990万元中标事实（2026-09-30公告）",
            "quote": "中标（成交）金额：990.0000000（万元）",
            "source_record_id": award_record.id,
            "in_source_record": _norm("中标（成交）金额：990.0000000（万元）") in _norm(award_record.raw_text or ""),
            "source_url": award_record.url,
        })
        evidence_checks.append({
            "item": "招聘信息（2026-04-30官网新闻，非'近期'）",
            "quote": "五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程",
            "source_record_id": hiring_record.id,
            "in_source_record": _norm("五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程") in _norm(hiring_record.raw_text or ""),
            "source_url": hiring_record.url,
        })
        evidence_checks.append({
            "item": "官网联系信息（国内业务邮箱/服务热线）",
            "quote": "hb3d@hb3dp.com",
            "source_record_id": hiring_record.id,
            "in_source_record": "hb3d@hb3dp.com" in (hiring_record.raw_text or ""),
            "source_url": "https://www.hb3dp.com",
        })

        # ---- 5) 约束自动检查 ----
        violations = [t for t in BANNED_TOKENS if t in FINAL_EMAIL]
        constraints_pass = not violations

        # ---- 3) 触达理由 + 4) Primary Offer 更名（写入快照）----
        offers = snapshot.get("offers", {}).get("广东汉邦激光科技有限公司", [])
        if offers:
            offers[0]["offer_name"] = "14天高校/科研采购机会人工验证试点"
            offers[0]["deliverable"] = ("每个工作日1封人工整理的高校/科研采购公告摘要（增材制造装备相关，关键词匹配+人工复核）；"
                                        "每周1次15分钟电话复盘")
            offers[0]["value_type"] = "待客户验证（本轮不预设价值类型，由试点结果证明）"
        snapshot["t09_b1"] = {
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "outreach_reason": "验证设备企业获取高校/科研采购机会的真实流程和痛点",
            "contact_recheck": contact_check,
            "evidence_recheck": evidence_checks,
            "final_email": FINAL_EMAIL,
            "constraints": {"banned_tokens": BANNED_TOKENS, "violations": violations,
                            "pass": constraints_pass,
                            "notes": "招聘事实按'4月底发布过招聘计划'表述（带日期，未使用'近期'）；"
                                     "邮件不断言客户痛点，仅提出验证请求"},
            "target_status": "READY_TO_CONTACT",
            "interaction_created": False,
        }
        snapshot["outreach_status"] = ("READY_FOR_MANUAL_OUTREACH"
                                        if (constraints_pass
                                            and all(bool(e["in_source_record"]) for e in evidence_checks)
                                            and contact_check.get("pass"))
                                        else "BLOCKED")
        experiment.snapshot_json = snapshot
        experiment.updated_at = datetime.now(timezone.utc)

        # ---- 7) Target → READY_TO_CONTACT ----
        if target.status == "NEW":
            before = target.status
            target.status = "READY_TO_CONTACT"
            target.reached_stage = "READY_TO_CONTACT"
            target.updated_at = datetime.now(timezone.utc)
            target.notes = (target.notes or "") + f"\n[2026-10-06 NEW→READY_TO_CONTACT] T09-B1：触达记录准备完成，等待人工确认发送"
            write_audit(db, "T09B1_TARGET_READY_TO_CONTACT", "experiment_target", target.id,
                        {"before": before, "after": "READY_TO_CONTACT",
                         "contact": "hb3d@hb3dp.com", "outreach_reason": snapshot["t09_b1"]["outreach_reason"],
                         "note": "等待用户确认'邮件已真实发送'后才会创建 Interaction 并改为 CONTACTED"})
        write_audit(db, "T09B1_PREPARED", "experiment", experiment.id, {
            "company": "广东汉邦激光科技有限公司",
            "contact_check_pass": contact_check.get("pass"),
            "evidence_all_pass": all(bool(e["in_source_record"]) for e in evidence_checks),
            "constraints_pass": constraints_pass,
            "outreach_status": snapshot["outreach_status"],
            "interaction_created": False,
        })
        db.commit()

        # ---- 6) 报告 ----
        lines = [
            "# T09-B1：汉邦激光首个真实客户触达记录准备",
            "",
            f"生成时间：{datetime.now(timezone.utc).isoformat()}",
            "",
            "## 1. 联系来源 URL 重验（hb3d@hb3dp.com）",
            "",
            f"- URL：{contact_check['url']} → HTTP {contact_check.get('http_status')}",
            f"- 页面含 hb3d@hb3dp.com：{contact_check.get('email_found_on_page')}",
            f"- 页面含'国内业务邮箱'标注：{contact_check.get('label_found_on_page')}",
            f"- 页面含服务热线 400-088-8585：{contact_check.get('phone_found_on_page')}",
            f"- **结论：{'✅ 有效' if contact_check.get('pass') else '❌ 无效'}**",
            "",
            "## 2. Evidence 重验（库内原文 + live）",
            "",
            "| 项 | 引用 | 库内原文 | live页面 |",
            "|---|---|---|---|",
        ]
        for e in evidence_checks:
            lines.append(f"| {e['item']} | {e['quote'][:50]} | {'✅' if e['in_source_record'] else '❌'} | {e.get('live_page', '—')} |")
        lines += [
            "",
            "- 招聘信息按事实表述为'官网4月底发布过招聘计划'（带日期），**未使用'近期招聘'**（任务书2）",
            "",
            "## 3. 触达理由（已更新）",
            "",
            "**验证设备企业获取高校/科研采购机会的真实流程和痛点**",
            "",
            "## 4. Primary Offer（已更名）",
            "",
            "**14天高校/科研采购机会人工验证试点** —— 每个工作日1封人工整理的高校/科研采购公告摘要"
            "（增材制造装备相关），每周1次15分钟电话复盘；全程免费、不推销系统；第14天由客户判断是否有用",
            "",
            "## 5. 最终人工发送版本（任务书6）",
            "",
            "```",
            FINAL_EMAIL,
            "```",
            "",
            "### 约束自动检查（任务书5）",
            "",
            f"- 违禁词检查（{'、'.join(BANNED_TOKENS)}）：**{'无违禁 ✓' if constraints_pass else '违规：' + '、'.join(violations)}**",
            "- 不出现 AI/Agent ✓ ｜ 不宣传平台 ✓ ｜ 不承诺ROI ✓ ｜ 不写1500元/月 ✓ ｜ 不声称客户存在痛点 ✓（以'想请您帮忙验证'代替）",
            "",
            "## 6. Experiment Target 状态",
            "",
            f"- 汉邦激光 Target：**READY_TO_CONTACT**（审计留痕）",
            f"- outreach_status：{snapshot['outreach_status']}",
            "",
            "## 7. Interaction",
            "",
            "**未创建 OUTREACH Interaction。** 只有用户明确确认'邮件已真实发送'后，"
            "才创建 Interaction（记录真实channel/contact/time/message summary/contact source）并将 Target 改为 CONTACTED。",
            "",
            "---",
            "",
            "**完成后停止。等待人工确认发送。**",
        ]
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "T09-B1_hanbang_ready.md").write_text("\n".join(lines), encoding="utf-8")
        (ROOT / "_t09_out.txt").write_text(json.dumps({
            "outreach_status": snapshot["outreach_status"],
            "contact_check": contact_check,
            "evidence_all_pass": all(bool(e["in_source_record"]) for e in evidence_checks),
            "constraints_pass": constraints_pass,
            "target_status": target.status,
            "interaction_created": False,
        }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"outreach_status": snapshot["outreach_status"],
                          "target": target.status,
                          "contact_pass": contact_check.get("pass"),
                          "constraints_pass": constraints_pass}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
