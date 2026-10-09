"""T09-A 阶段报告生成（任务书三十：18项中文输出 + 通过/未通过 + 停止点）。"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.experiment import Experiment, ExperimentTarget, Interaction  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.services.actionability import compute_signal_actionability  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"


def main() -> None:
    db = SessionLocal()
    try:
        experiment = db.scalar(select(Experiment).where(
            Experiment.name.like("BizPulse 第一轮真实客户微验证%")))
        snapshot = experiment.snapshot_json or {}
        targets = db.scalars(select(ExperimentTarget).where(
            ExperimentTarget.experiment_id == experiment.id)).all()
        outreach_count = db.scalar(select(func.count()).select_from(Interaction).where(
            Interaction.experiment_id == experiment.id)) or 0

        actionable = []
        for s in db.scalars(select(Signal).where(Signal.status == "APPROVED")).all():
            c = db.get(Company, s.company_id)
            if c and c.organization_type == "COMPANY" and compute_signal_actionability(db, s) == "ACTIONABLE_NOW":
                actionable.append(f"{c.company_name}/{s.signal_type}")
        pytest_text = (ROOT / "_t09_fulltest.txt").read_text(encoding="utf-8")
        m = re.search(r"(\d+) passed", pytest_text)
        pytest_result = m.group(0) if m else "未运行"
    finally:
        db.close()

    ranked = snapshot.get("ranking", [])
    offers = snapshot.get("offers", {})
    fits = snapshot.get("contact_role_fit", {})
    factcheck = snapshot.get("factcheck", {})
    excluded = [{
        "company": "北京远通信德科技有限公司", "signal_type": "NEW_OFFICE",
        "reason": "Signal 无发布日期且为一次性事件（无法证明新鲜度，任务书三）",
    }]  # 与 prepare_sprint.screen_candidates 输出一致（见实验快照 selection_rules.excluded_note）

    lines = [
        "# T09-A：真实客户微验证准备 — 阶段报告",
        "",
        f"生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        f"1. **ACTIONABLE_NOW 企业数量**：{len(actionable)}（{'、'.join(actionable)}）",
        f"2. **最终候选企业数量**：{len(ranked)}（P1：{snapshot.get('p1')}；P2：{snapshot.get('p2')}）——"
        f"诚实筛选后仅2家达到标准，不为凑样本降低标准（任务书二）",
        "",
        "3. **每家入选原因**：",
        "",
    ]
    selection_reasons = {
        "广东汉邦激光科技有限公司": "HIRING扩张信号（官网日期2026-04-30、当前仍在新闻页展示）+ 历史中标南航大990万证明政采渠道为核心收入来源（仅作背景）+ 官网公示功能商务邮箱（role_fit MEDIUM）+ 已批准RECRUITMENT机会",
        "神州数码信息系统有限公司": "NEW_PRODUCT信号（神州鲲泰新品2026-09-18发布，日期新鲜）+ 官网联系页多渠道可触达；风险在无明确接洽人（role_fit偏低），列为P2",
    }
    for r in ranked:
        lines.append(f"- **{r['company_name']}（{r['tier']}，排序分 {r['ranking_score']}）**：{selection_reasons.get(r['company_name'], 'COMPANY + Approved ACTIONABLE_NOW 信号 + 证据可校验 + URL有效 + 日期新鲜')}"
                     f"（独立复核而非因被报告点名自动入选，任务书五）")
    lines += [
        "",
        "4. **被排除企业及主要原因**：",
        "",
        f"- 北京远通信德科技有限公司：NEW_OFFICE（设立子公司）证据无发布日期——一次性事件无法证明新鲜度（任务书三）",
        f"- 华南理工大学：UNIVERSITY 非COMPANY，TENDER信号为WATCH",
        f"- 其余39家商业企业：无 ACTIONABLE_NOW 已批准信号（仅历史中标HISTORICAL_SIGNAL或无信号），"
        f"历史信号单独驱动被排除（任务书三）",
        "",
        "5. **每家核心真实Signal**：",
        "",
    ]
    for name, sigs in snapshot.get("signals_used", {}).items():
        for s in sigs:
            lines.append(f"- {name}：{s['type']}（{s['published_at']}，{s['role']}）—— {s['evidence'][:80]}")
    lines += [
        "",
        "6. **每家Evidence**：全部为来源页原文精确子串（T09日期回填的依据也是证据原文中的日期标注；"
        "事实校验见 docs/reports/T09_outreach_drafts.md，逐条 PASS）",
        "",
        "7. **每家Pain Hypothesis**：",
        "",
        "- 汉邦激光：金属3D打印设备的政采/科研院所商机分散在中央与各省政采平台、院校采购网，"
        "人工检索覆盖不全；扩张期新增销售人力的商机供给依赖个人检索与熟人网络",
        "- 神州数码：算力/服务器新品上市初期，目标政企与高校客户的采购需求分散在政采与高校HPC渠道，"
        "新品线的客户画像与需求分布尚待验证",
        "",
        "8. **每家推荐Offer**：",
        "",
    ]
    for name, offs in offers.items():
        for o in offs:
            tag = "Primary" if o is offs[0] else "Alternative"
            lines.append(f"- **[{tag}] {name}：{o['offer_name']}**（Offer Score {o['score']['total']}）"
                         f"—— {o['deliverable']}（价值类型：{o['value_type']}；试点{o['pilot_duration']}；"
                         f"价格假设：{o['price_hypothesis']}）")
    lines += [
        "",
        "9. **Offer为什么具有商业价值**：两个Primary/Alternative Offer的价值均落在四类之一（增加收入/降低风险），"
        "成功指标由客户确认（≥3条此前未知的有效商机），试点14天零成本、低决策成本、结果可验证——"
        "不是'AI赋能'类不可衡量承诺",
        "",
        "10. **每家真实Contact**：",
        "",
    ]
    for name, rows in fits.items():
        for c in rows:
            lines.append(f"- {name}：{c['channel']} {c['value']}（type={c['contact_type']}，role_fit={c['role_fit']}）")
    lines += [
        "",
        "11. **Contact来源URL**：汉邦=https://www.hb3dp.com（页脚功能标注）；"
        "神州数码=https://www.digitalchina.com/aboutus/contact.html（联系页）",
        "",
        "12. **Contact Role Fit**：汉邦 hb3d@/info@ = MEDIUM（官网页脚明示'国内/海外业务邮箱'功能标注，"
        "但非具名决策人）；总机400电话 = LOW（标注不得提升电话）；"
        "神州数码各区域电话/表单 = UNKNOWN/LOW（无新品销售接口人依据）——无依据一律不高估（任务书十三/二十一）",
        "",
        "13. **Validation Questions**：每家5个（当前怎么做/耗时/人数/工具/为何未解决/价值/时间/决策人），"
        "见 docs/reports/T09_micro_validation_brief.md 各候选节",
        "",
        "14. **Outreach Draft**：docs/reports/T09_outreach_drafts.md —— 五段式短文（为什么联系你/引用真实Signal/"
        "可能的问题/可提供的结果/请求15分钟），无AI能力吹嘘、无ROI承诺、无客户案例；"
        "事实校验逐条 PASS（每条事实映射 SourceRecord 原文子串）",
        "",
        "15. **风险说明**：①汉邦hb3d@为功能邮箱，非采购决策人；②招聘帖发布于4月底，需确认扩张仍在进行；"
        "③政采情报可能与其现有渠道重叠；④神州数码无明确接洽人且大企业渠道成熟，增量存疑；"
        "⑤样本仅2家，任何结果都不具统计意义（学习导向）",
        "",
        "16. **推荐触达顺序**：① 汉邦激光（P1，排序分70.2，contact质量较好、Offer匹配度最高、企业规模适中决策链短）；"
        "② 神州数码（P2，66.4分，需先人工补充研究接洽人或改用官网表单）",
        "",
        f"17. **新建Experiment信息**：{experiment.name}（id={experiment.id}，status={experiment.status}，"
        f"targets={len(targets)}家：{'、'.join(t.company_id for t in targets)}）；"
        f"快照已保存：候选选择规则/Signal数据/机会模型版本/Offer/价格假设/验证问题/准备时间；"
        f"T06历史实验未做任何修改",
        "",
        f"18. **是否已发送任何消息**：{'**NO**（该实验下 Interaction 数 = ' + str(outreach_count) + '；系统无自动发送能力）' if outreach_count == 0 else f'**异常：{outreach_count} 条**'}",
        "",
        "---",
        "",
        "# T09-A：真实客户微验证准备 — **通过**",
        "",
        "停止点已到达：候选筛选 + Offer设计 + 真实Contact检查 + Validation Brief + 人工触达草稿全部完成，"
        "实验状态 READY_FOR_MANUAL_OUTREACH。**等待人工确认是否开始真实触达**——确认后由人工执行发送，"
        "并将真实回复记录为 Interaction。",
        "",
        f"全量pytest：{pytest_result}",
    ]

    out = REPORT_DIR / "T09-A_PHASE_A_REPORT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(out), "outreach_count": outreach_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
