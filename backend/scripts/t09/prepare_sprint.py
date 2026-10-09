"""T09-A 微型验证 Sprint 准备（任务书三~十九、二十九）。

流程：硬筛 → 加权排序 → Offer设计（≤3/家）+ Offer Score → Validation Brief
→ 人工触达草稿（逐条事实校验）→ 新建 Micro Validation Experiment（含快照）
→ 状态置 READY_FOR_MANUAL_OUTREACH 后停止（禁止发送）。

产出：
- docs/reports/T09_micro_validation_brief.md
- docs/reports/T09_outreach_drafts.md
- Experiment（正式库，status=READY，快照含 selection rules / signals / offers / questions）
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
from app.models.company import Company, CompanyContact  # noqa: E402
from app.models.experiment import Experiment, ExperimentTarget  # noqa: E402
from app.models.opportunity import Opportunity  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.services.audit import write_audit  # noqa: E402
from app.services.micro_validation import (  # noqa: E402
    RANKING_WEIGHTS,
    contact_channel,
    contact_role_fit,
    factcheck_claims,
    rank_micro_candidates,
    score_offer,
    screen_candidates,
)

REPORT_DIR = ROOT / "docs" / "reports"


def _company(db, name: str) -> Company:
    return db.scalar(select(Company).where(Company.company_name == name))


def _signal(db, company: Company, signal_type: str) -> Signal | None:
    return db.scalar(select(Signal).where(
        Signal.company_id == company.id, Signal.signal_type == signal_type,
        Signal.status == "APPROVED"))


def _opp_components(db, company_id: str) -> dict:
    """从该企业已批准机会读取真实评分组件。"""
    opp = db.scalar(select(Opportunity).where(
        Opportunity.company_id == company_id,
        Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE"))
    if opp is None:
        return {}
    try:
        breakdown = json.loads(opp.score_breakdown_json) if isinstance(opp.score_breakdown_json, str) else (opp.score_breakdown_json or {})
        return {
            "pain": round(breakdown.get("pain", {}).get("score", 0)),
            "intent": round(breakdown.get("intent", {}).get("score", 0)),
            "evidence": round(breakdown.get("evidence", {}).get("score", 0)),
            "agent_fit": round(breakdown.get("agent_fit", {}).get("score", 0)),
        }
    except Exception:  # noqa: BLE001
        return {}


def _reachability_sub(db, company_id: str) -> int:
    from app.analyzers.opportunity.context import load_company_context
    from app.analyzers.opportunity.reachability import compute_reachability

    ctx = load_company_context(db, company_id)
    return compute_reachability(ctx).score if ctx else 0


def build_candidates(db) -> tuple[list[dict], list[dict]]:
    passed, excluded = screen_candidates(db)
    candidates = []
    for p in passed:
        comps = _opp_components(db, p["company_id"])
        subs = {
            "actionability": 100,  # 硬筛通过即 ACTIONABLE_NOW
            "pain_strength": comps.get("pain") or min(90, max(s["confidence"] for s in p["signals"])),
            "intent": comps.get("intent", 0),  # 无直接购买信号时如实为 0/低分
            "evidence": comps.get("evidence") or 70,  # 无机会时按来源等级（B级 → 70）
            "reachability": _reachability_sub(db, p["company_id"]),
            "solution_fit": comps.get("agent_fit") or 42,  # 无机会时用先验适配值（客户获取类 42）
        }
        opp = db.scalar(select(Opportunity).where(
            Opportunity.company_id == p["company_id"],
            Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE"))
        candidates.append({**p, "subs": subs, "opportunity_id": opp.id if opp else None})
    return candidates, excluded


# ---------------------------------------------------------------------------
# Sprint 结构化数据（Offer / Brief / 草稿 / 问题）—— 全部锚定真实证据
# ---------------------------------------------------------------------------

def sprint_data(db) -> dict:
    data: dict = {}

    hanbang = _company(db, "广东汉邦激光科技有限公司")
    hb_hiring = _signal(db, hanbang, "HIRING")
    hb_award = _signal(db, hanbang, "CONTRACT_AWARD")
    hb_record_id = hb_hiring.source_record_id
    award_record_id = hb_award.source_record_id

    data["广东汉邦激光科技有限公司"] = {
        "tier": "P1",
        "signals": [
            {"signal_id": hb_hiring.id, "type": "HIRING", "published_at": "2026-04-30",
             "evidence": (hb_hiring.description or "")[:120], "role": "主信号（当前扩张行为）"},
            {"signal_id": hb_award.id, "type": "CONTRACT_AWARD", "published_at": "2026-09-30",
             "evidence": (hb_award.description or "")[:120],
             "role": "背景证据（历史中标，证明政采渠道为核心收入来源；不作为当前意图）"},
        ],
        "why_now": "招聘campaign（4月底发布，官网新闻页当前仍在展示）表明销售/业务组织正在扩张；"
                   "叠加2026年9月底中标南航大990万增材制造平台（背景），公司处于拿单能力扩张期——"
                   "此时销售端对'更多合格商机'的需求最真实",
        "pain_hypothesis": "金属3D打印设备的政府采购/科研院所商机分散在中央与各省政采平台、院校采购网，"
                           "人工检索覆盖不全；扩张期新增销售人力的商机供给依赖个人检索与熟人网络",
        "contact_basis": "官网页脚明示：国内业务邮箱 hb3d@hb3dp.com、海外业务邮箱 info@hb3dp.com、服务热线 400-088-8585",
        "offers": [
            {
                "offer_id": "OFFER-HB-1",
                "offer_name": "政采商机情报 · 14天免费试点（金属3D打印品类）",
                "target_customer": "广东汉邦激光科技有限公司（国内销售/市场团队）",
                "trigger": "HIRING（2026-04-30 招聘campaign）+ 背景中标南航大990万（政采渠道为核心收入来源）",
                "problem_hypothesis": "设备品类政采商机分散在中央/省级政采平台与院校采购网，人工检索覆盖不全，扩张期商机供给不足",
                "deliverable": "每个工作日1封邮件：与增材制造装备相关的全国政采公告摘要（关键词匹配+人工复核）；每周1次15分钟匹配度复盘",
                "expected_value_direction": "增加收入（新增合格商机线索）",
                "pilot_scope": "仅政府采购公开渠道；仅激光/增材/3D打印装备品类；最多2个收件人",
                "pilot_duration": "14天",
                "pilot_duration_days": 14,
                "price_hypothesis": "试点期0元；验证通过后的续费假设为1,500元/月/品类（仅为实验假设，非市场定价）",
                "success_metric": "试点期内≥3条公告被贵司销售确认为此前未知的有效商机（由客户确认，非我方判定）",
                "risk": "商机可能与其现有渠道重叠；hb3d@为功能邮箱非具名决策人；招聘帖发布于4月底，需确认扩张仍在进行",
                "value_type": "增加收入",
                "pain_match_score": 85, "urgency_score": 55, "delivery_feasibility_score": 85,
                "buyer_clarity": "MEDIUM",
            },
            {
                "offer_id": "OFFER-HB-2",
                "offer_name": "已中标客户复购与竞标动态监测（最多5家院校）",
                "target_customer": "广东汉邦激光科技有限公司（销售/大客户团队）",
                "trigger": "背景：南航大990万已交付客户；政采客户复购/竞品渗透无系统监测",
                "problem_hypothesis": "已中标院校的后续采购与竞品中标动态没有系统监测，复购机会依赖客户主动联系",
                "deliverable": "14天内监测已中标院校的新采购公告与相关设备竞标结果，出现匹配事件即时提醒",
                "expected_value_direction": "增加收入（复购/追加采购）+ 降低风险（客户被竞品渗透预警）",
                "pilot_scope": "最多5家已中标客户院校；仅公开公告渠道",
                "pilot_duration": "14天",
                "pilot_duration_days": 14,
                "price_hypothesis": "试点0元；转正假设800元/月/5客户（实验假设）",
                "success_metric": "≥1条复购线索或竞品动态被销售确认有价值",
                "risk": "设备类复购周期长，14天窗口可能无事件发生（学习型验证）",
                "value_type": "增加收入",
                "pain_match_score": 70, "urgency_score": 45, "delivery_feasibility_score": 90,
                "buyer_clarity": "MEDIUM",
            },
        ],
        "discovery_questions": [
            "贵司现在怎么发现政采/科研院所的设备采购机会？由谁负责？",
            "每周大约花多少时间人工检索和筛选这些公告？有没有漏掉过重要公告？",
            "新销售的商机从哪里来（展会/老客户/招标平台）？上手最慢的环节是什么？",
            "如果每天有自动推送的匹配公告，由谁判断'值不值得跟'？判断标准是什么？",
            "最近一次因为信息晚到而错过（或差点错过）的订单是什么情况？",
        ],
        "draft_claims": [
            {"claim": "贵司官网4月底发布招聘计划（五一诚邀英才）",
             "quote": "五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程",
             "source_record_id": hb_record_id},
            {"claim": "贵司2026年9月30日发布公告，中标南京航空航天大学增材制造平台项目（990万元）",
             "quote": "中标（成交）金额：990.0000000（万元）",
             "source_record_id": award_record_id},
        ],
    }

    dc = _company(db, "神州数码信息系统有限公司")
    dc_newprod = _signal(db, dc, "NEW_PRODUCT")
    dc_record_id = dc_newprod.source_record_id

    data["神州数码信息系统有限公司"] = {
        "tier": "P2",
        "signals": [
            {"signal_id": dc_newprod.id, "type": "NEW_PRODUCT", "published_at": "2026-09-18",
             "evidence": (dc_newprod.description or "")[:120], "role": "主信号（新品上市）"},
        ],
        "why_now": "神州鲲泰新一代产品矩阵（鲲鹏/昇腾路线）9月18日刚发布——新品上市初期是验证目标行业需求分布、"
                   "补齐首批客户线索的窗口期",
        "pain_hypothesis": "算力/服务器新品上市初期，目标政企与高校客户的采购需求分散在政采与高校HPC渠道，"
                           "新品线的客户画像与需求分布尚待验证",
        "contact_basis": "官网联系页公示各区域联系电话与联系表单；另有培训线邮箱 dctraining@dcclouds.com——"
                         "无明确新品销售接口人（role_fit 偏低，需人工补充研究或改用表单）",
        "offers": [
            {
                "offer_id": "OFFER-DC-1",
                "offer_name": "算力设备政采需求监测 · 14天诊断报告",
                "target_customer": "神州数码信息系统有限公司（神州鲲泰产品线）",
                "trigger": "NEW_PRODUCT（2026-09-18 神州鲲泰新一代产品矩阵发布）",
                "problem_hypothesis": "新品上市初期需要验证目标行业需求分布；算力设备采购需求分散在政采与高校HPC渠道",
                "deliverable": "14天诊断：全国政采渠道中算力/服务器/信创设备采购公告分布地图 + 10条高匹配线索样例",
                "expected_value_direction": "增加收入（新品目标客户线索）",
                "pilot_scope": "仅公开政采渠道；仅算力/服务器品类",
                "pilot_duration": "14天",
                "pilot_duration_days": 14,
                "price_hypothesis": "诊断报告固定价5,000元（实验假设，非市场定价）",
                "success_metric": "10条线索中≥3条被产品/销售团队确认匹配目标客户画像",
                "risk": "大企业自有渠道成熟，增量价值存疑；无明确接洽人（role_fit UNKNOWN/LOW）；"
                        "AI转型类信号不作为卖点（该企业是AI服务供给方）",
                "value_type": "增加收入",
                "pain_match_score": 60, "urgency_score": 70, "delivery_feasibility_score": 80,
                "buyer_clarity": "LOW",
            },
        ],
        "discovery_questions": [
            "神州鲲泰新品的目标客户画像由谁定义？现在如何获取首批客户线索？",
            "政企/高校算力采购信息现在由谁跟踪？用什么工具？",
            "新品上市90天内，市场/销售最缺的是哪一类信息？",
            "如果有一份全国算力采购需求分布地图，谁会用它做什么决策？",
            "这类诊断报告在贵司的采购流程里由谁拍板？预算走哪个科目？",
        ],
        "draft_claims": [
            {"claim": "贵司旗下神州鲲泰于9月18日发布新一代产品矩阵（鲲鹏、昇腾技术路线）",
             "quote": "神州数码旗下神州鲲泰正式推出基于鲲鹏、昇腾950技术路线的新一代产品矩阵",
             "source_record_id": dc_record_id},
        ],
    }
    return data


def main() -> None:
    db = SessionLocal()
    try:
        candidates, excluded = build_candidates(db)
        data = sprint_data(db)

        # 联系人 role_fit（公开字段规则 + 来源页功能标注作为依据）
        contact_view: dict[str, list] = {}
        for name in data:
            company = _company(db, name)
            rows = db.scalars(select(CompanyContact).where(CompanyContact.company_id == company.id)).all()
            label_basis = data[name]["contact_basis"] if name == "广东汉邦激光科技有限公司" else None
            contact_view[name] = []
            for c in rows:
                contact_view[name].append({
                    "contact_id": c.id, "channel": contact_channel(c),
                    "value": c.email or c.phone or c.public_profile_url,
                    "contact_type": c.contact_type,
                    "role_fit": contact_role_fit(c, label_basis=label_basis),
                })

        ranked = rank_micro_candidates(db, [
            {"company_id": c["company_id"], "company_name": c["company_name"],
             "signals": c["signals"], "subs": c["subs"],
             "tier": data[c["company_name"]]["tier"],
             "why_now": data[c["company_name"]]["why_now"],
             "pain_hypothesis": data[c["company_name"]]["pain_hypothesis"],
             "opportunity_id": c.get("opportunity_id")}
            for c in candidates
        ])

        for payload in data.values():
            for offer in payload["offers"]:
                offer["score"] = score_offer(offer)

        factchecks = {name: factcheck_claims(db, payload["draft_claims"]) for name, payload in data.items()}
        all_pass = all(f["pass"] for checks in factchecks.values() for f in checks)

        # ---- 新建 Micro Validation Experiment（不动 T06 历史实验）----
        exp_name = "BizPulse 第一轮真实客户微验证 #1：装备制造政采商机情报"
        exp = db.scalar(select(Experiment).where(Experiment.name == exp_name))
        created = False
        hanbang = _company(db, "广东汉邦激光科技有限公司")
        if exp is None:
            primary_offer = data["广东汉邦激光科技有限公司"]["offers"][0]
            exp = Experiment(
                name=exp_name,
                hypothesis="有真实扩张/中标信号的装备制造企业，在收到与其品类匹配的政采商机推送后，"
                           "会确认商机价值并愿意继续交流（14天试点）",
                target_customer="有政采中标历史的装备制造企业（第一批：金属3D打印/增材制造）",
                value_proposition="把分散的政府采购商机变成每天送到销售的线索清单",
                offer_description=f"{primary_offer['offer_name']}：{primary_offer['deliverable']}",
                price_amount=0, price_currency="CNY", price_type="PILOT",
                target_company_count=2, target_contacts=2,
                target_replies=1, target_meetings=1,
                target_quotes=0, target_pilots=0, target_wins=0,
                success_criteria="至少1家企业进入有效商业对话（回复并确认交流意愿）；"
                                 "或获得明确拒绝原因；或证伪某一Pain假设——三者都算有效学习",
                status="READY",
            )
            db.add(exp)
            db.flush()
            created = True

        snapshot = {
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "outreach_status": "READY_FOR_MANUAL_OUTREACH" if all_pass else "BLOCKED_FACTCHECK",
            "selection_rules": {
                "hard_filter": "organization_type=COMPANY + Approved Signal + actionability=ACTIONABLE_NOW + "
                               "Evidence原文可校验 + SourceURL有效 + Signal新鲜（有日期，或进行中行为类且官网在展示）",
                "excluded_note": "无日期的一次性事件（如'设立子公司'）不通过新鲜度筛选",
                "ranking_weights": RANKING_WEIGHTS,
            },
            "ranking": [{k: r[k] for k in ("rank", "company_name", "ranking_score", "tier", "subs")}
                        for r in ranked],
            "signals_used": {name: payload["signals"] for name, payload in data.items()},
            "opportunity_model": "T05 generator + T08.2 actionability 门（bundles/_is_current_signal）",
            "offers": {name: payload["offers"] for name, payload in data.items()},
            "discovery_questions": {name: payload["discovery_questions"] for name, payload in data.items()},
            "contact_role_fit": contact_view,
            "factcheck": factchecks,
            "p1": ["广东汉邦激光科技有限公司"],
            "p2": ["神州数码信息系统有限公司"],
            "experiment_scale_note": "本轮最多2家（任务书十九：P1≤3、P2≤2；先学习再扩）",
            "target_added": "仅汉邦激光（其机会已人工批准）；神州数码无已批准机会，P2 待人工决定后再入池",
        }
        exp.snapshot_json = snapshot
        exp.updated_at = datetime.now(timezone.utc)

        # Target：仅 P1 汉邦（需已批准机会）
        hanbang_opp = db.scalar(select(Opportunity).where(
            Opportunity.company_id == hanbang.id,
            Opportunity.review_status == "APPROVED", Opportunity.status == "ACTIVE"))
        if hanbang_opp is not None:
            existing_target = db.scalar(select(ExperimentTarget).where(
                ExperimentTarget.experiment_id == exp.id,
                ExperimentTarget.company_id == hanbang.id))
            if existing_target is None:
                db.add(ExperimentTarget(
                    experiment_id=exp.id, company_id=hanbang.id,
                    opportunity_id=hanbang_opp.id, priority=1, status="NEW",
                    added_at=datetime.now(timezone.utc),
                    selection_reason=json.dumps(
                        ["P1唯一候选", "HIRING扩张信号+政采中标背景+功能商务邮箱MEDIUM"], ensure_ascii=False),
                ))
                write_audit(db, "T09_TARGET_ADDED", "experiment_target", exp.id,
                            {"company_id": hanbang.id, "opportunity_id": hanbang_opp.id, "tier": "P1"})
        write_audit(db, "T09_SPRINT_PREPARED", "experiment", exp.id, {
            "experiment": exp.name, "status": exp.status,
            "outreach_status": snapshot["outreach_status"],
            "candidates": [r["company_name"] for r in ranked],
        })
        db.commit()

        write_brief_markdown(ranked, data, contact_view, excluded)
        write_draft_markdown(data, factchecks)
        summary = {
            "experiment": exp.name, "experiment_id": exp.id, "created": created,
            "outreach_status": snapshot["outreach_status"],
            "ranked": [(r["rank"], r["company_name"], r["ranking_score"]) for r in ranked],
            "excluded": excluded,
            "factcheck_all_pass": all_pass,
        }
        (ROOT / "_t09_out.txt").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str),
                                           encoding="utf-8")
        print(json.dumps({"outreach_status": snapshot["outreach_status"],
                          "ranked": [(r["company_name"], r["ranking_score"]) for r in ranked],
                          "excluded": len(excluded)}, ensure_ascii=False))
    finally:
        db.close()


def write_brief_markdown(ranked, data, contact_view, excluded) -> None:
    lines = [
        "# T09 微型验证候选简报（Micro Validation Brief）",
        "",
        f"生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 候选排序（任务书四：Actionability30/Pain20/Intent15/Evidence15/Reach10/Fit10）",
        "",
        "| 排名 | 企业 | 档位 | 排序分 | 子分 |",
        "|---|---|---|---|---|",
    ]
    for r in ranked:
        lines.append(f"| {r['rank']} | {r['company_name']} | {r['tier']} | {r['ranking_score']} | "
                     f"{json.dumps(r['subs'], ensure_ascii=False)} |")
    lines += ["", "## 被排除企业及原因", ""]
    for e in excluded:
        lines.append(f"- {e['company']}（{e['signal_type']}）：{e['reason']}")
    lines.append("- 其余39家商业企业：无 ACTIONABLE_NOW 已批准信号（仅历史中标/无信号）——不入选")
    lines.append("- 华南理工大学：UNIVERSITY（非COMPANY），其TENDER信号为WATCH")

    for r in ranked:
        name = r["company_name"]
        payload = data[name]
        primary = payload["offers"][0]
        alt = payload["offers"][1] if len(payload["offers"]) > 1 else None
        lines += [
            "", "---", "", f"# 候选：{name}（{r['tier']}，排序分 {r['ranking_score']}）",
            "",
            f"【企业】{name}",
            "【真实变化】" + "；".join(
                f"{s['type']}（{s['published_at']}）{(s['evidence'] or '')[:70]}" for s in payload["signals"]),
            "【证据】" + "；".join(f"{s['type']}：{(s['evidence'] or '')[:100]}" for s in payload["signals"]),
            f"【为什么现在】{payload['why_now']}",
            f"【AI推断的Pain】{payload['pain_hypothesis']}",
            "【需要验证的问题】",
        ]
        lines += [f"- {q}" for q in payload["discovery_questions"]]
        lines += [
            f"【推荐Offer（Primary）】{primary['offer_name']}",
            f"- 目标客户：{primary['target_customer']}",
            f"- 触发：{primary['trigger']}",
            f"- 问题假设：{primary['problem_hypothesis']}",
            f"- 交付物：{primary['deliverable']}",
            f"- 价值方向：{primary['expected_value_direction']}（价值类型：{primary['value_type']}）",
            f"- 试点范围/时长：{primary['pilot_scope']} / {primary['pilot_duration']}",
            f"- 价格假设：{primary['price_hypothesis']}",
            f"- 成功指标：{primary['success_metric']}",
            f"- Offer Score：{primary['score']['total']}（{json.dumps(primary['score']['dims'], ensure_ascii=False)}）",
            "【Alternative Offer】" + (
                f"{alt['offer_name']}（{alt['score']['total']}分）" if alt else "无"),
            f"【潜在价值】{primary['expected_value_direction']}",
            "【真实公开Contact】",
        ]
        for c in contact_view[name]:
            lines.append(f"- {c['channel']} {c['value']}（type={c['contact_type']}，role_fit={c['role_fit']}）")
        lines += [
            f"【Contact来源】{payload['contact_basis']}",
            f"【风险】{primary['risk']}",
            "【禁止声称的内容】不得声称客户已有采购意向/预算；不得引用未验证的客户案例；"
            "不得使用'AI赋能''数字化升级'等不可衡量价值作为核心卖点；历史中标仅作背景，不得暗示当前采购",
        ]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "T09_micro_validation_brief.md").write_text("\n".join(lines), encoding="utf-8")


def write_draft_markdown(data, factchecks) -> None:
    drafts_text = {
        "广东汉邦激光科技有限公司": (
            "主题：给汉邦激光的14天政采商机测试（免费）\n\n"
            "您好：\n\n"
            "我们是 BizPulse（商脉），做政府采购商机情报的整理与推送。\n\n"
            "【为什么联系你】注意到贵司今年4月底在官网发布了招聘计划，同时9月30日公告中标"
            "南京航空航天大学增材制造平台项目——我们在跟踪装备制造企业的政采商机动态。\n\n"
            "【一个可能的问题】金属3D打印设备的政采/科研商机分散在中央与各省政采平台和院校采购网，"
            "销售团队扩张时靠人工检索很难覆盖全。\n\n"
            "【我们可以先做的】未来14天，每个工作日给贵司推送一封与增材制造装备相关的全国采购公告摘要"
            "（免费），第14天用\"是否发现≥3条此前未知的有效商机\"来判断要不要继续。\n\n"
            "【请求】如果这个方向值得聊，希望约15分钟电话，先了解贵司现在怎么找这类商机。\n\n"
            "—— BizPulse（商脉）"
        ),
        "神州数码信息系统有限公司": (
            "主题：给神州鲲泰新品的14天政采需求诊断（可先看样例）\n\n"
            "您好：\n\n"
            "我们是 BizPulse（商脉），做政府采购商机情报的整理与推送。\n\n"
            "【为什么联系你】注意到贵司旗下神州鲲泰9月18日发布了新一代产品矩阵（鲲鹏、昇腾技术路线）。\n\n"
            "【一个可能的问题】算力/服务器新品上市初期，政企与高校的采购需求分散在各地政采与院校渠道，"
            "目标行业需求分布需要快速验证。\n\n"
            "【我们可以先做的】14天诊断：输出全国政采渠道中算力/服务器/信创设备采购公告的分布地图，"
            "附10条高匹配线索样例。\n\n"
            "【请求】如果这份诊断对神州鲲泰的市场团队有用，希望约15分钟电话沟通需求细节。\n\n"
            "—— BizPulse（商脉）"
        ),
    }
    lines = [
        "# T09 首轮人工触达草稿（READY_FOR_MANUAL_OUTREACH —— 禁止自动发送）",
        "",
        f"生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "**状态：等待人工确认。系统不含任何自动发送能力；发送须由人工执行。**",
        "",
    ]
    for name, payload in data.items():
        lines += [f"## {name}（{payload['tier']}）", "", "### 事实校验（任务书十六）", ""]
        for f in factchecks[name]:
            lines.append(f"- {'✅ PASS' if f['pass'] else '❌ FAIL'}：{f['claim']} ← 「{f['quote'][:60]}」")
        lines += ["", "### 触达草稿（建议渠道：EMAIL；收件人见 Brief Contact 节）", "", "```", drafts_text[name], "```", ""]
        lines += ["### Discovery Questions（人工沟通用）", ""]
        for i, q in enumerate(payload["discovery_questions"], 1):
            lines.append(f"{i}. {q}")
        lines.append("")
    (REPORT_DIR / "T09_outreach_drafts.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
