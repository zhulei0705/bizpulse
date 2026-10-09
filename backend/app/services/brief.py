"""T07 Validation Brief / Outreach Package / 实验报告。

原则：
- Brief 明确区分【事实】【AI推断】【待验证】三类（任务书二十）；
- Outreach Draft 只是草稿（不自动发送），话术围绕真实 Signal，禁止虚构个性化
  （任务书二十四/二十五/二十六）；
- Report 区分【真实结果】与【系统分析】（任务书五十五），LLM 只读、不修改任何结果。
"""
from __future__ import annotations

import io
import csv
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import REPLY_CATEGORIES
from app.models.company import Company, CompanyContact
from app.models.experiment import ExperimentOutcome, ExperimentTarget, Interaction
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.models.signal import Signal
from app.models.source import SourceRecord
from app.services.metrics import experiment_funnel, experiment_metrics

FACT = "事实"
INFERENCE = "AI推断"
TO_VALIDATE = "待验证"


def _aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _contact_line(contact: CompanyContact) -> dict:
    return {
        "name": contact.name,
        "title": contact.title,
        "email": contact.email or contact.public_contact,
        "phone": contact.phone,
        "public_profile_url": contact.public_profile_url,
        "verification_status": contact.verification_status,
        "source_url": contact.source_url,
    }


def build_validation_brief(db: Session, target: ExperimentTarget) -> dict:
    """Outreach Package（任务书三十/三十一）：公司简报 + 证据 + 联系人 + 草稿话术 + 验证问题。"""
    company = db.get(Company, target.company_id)
    opportunity = db.get(Opportunity, target.opportunity_id) if target.opportunity_id else None

    # 真实证据链（机会证据 → 信号 → 原文来源）
    facts: list[dict] = []
    evidences: list[dict] = []
    if opportunity:
        rows = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opportunity.id)).all()
        for e in rows:
            record = db.get(SourceRecord, e.source_record_id) if e.source_record_id else None
            signal = db.get(Signal, e.signal_id) if e.signal_id else None
            evidences.append({
                "excerpt": e.evidence_excerpt,
                "url": record.url if record else None,
                "signal_type": signal.signal_type if signal else None,
                "signal_title": signal.title if signal else None,
                "collected_at": signal.collected_at.isoformat() if signal and signal.collected_at else None,
            })
            if record and record.url:
                facts.append({
                    "kind": FACT,
                    "statement": f"公开来源（{record.url[:80]}）：{(e.evidence_excerpt or signal.title if signal else '') or ''}".strip("："),
                })
        # 问题/方案假设是 AI 推断（T05 生成），明确标注
        if opportunity.problem:
            facts.append({"kind": INFERENCE, "statement": f"AI推断（问题假设）：{opportunity.problem[:150]}"})
        if opportunity.why_now:
            facts.append({"kind": INFERENCE, "statement": opportunity.why_now})
        for risk in opportunity.risk_notes or []:
            facts.append({"kind": INFERENCE, "statement": f"风险提示：{risk}"})
    # Pain 假设是推断，最终结论待客户验证
    if opportunity:
        facts.append({"kind": TO_VALIDATE, "statement": f"待验证：{(opportunity.problem or '')[:120]}"})

    contacts = db.scalars(select(CompanyContact).where(CompanyContact.company_id == target.company_id)).all()
    usable_contacts = [
        _contact_line(c) for c in contacts
        if c.verification_status in {"VERIFIED_PUBLIC", "USER_PROVIDED"}
    ]

    draft = build_outreach_draft(db, target, company, opportunity, facts)

    return {
        "target_id": target.id,
        "experiment_id": target.experiment_id,
        "company": {
            "id": company.id, "name": company.company_name, "website": company.website,
            "industry": company.industry, "employee_range": company.employee_range,
            "description": company.company_description,
        } if company else None,
        "opportunity": {
            "id": opportunity.id, "title": opportunity.title,
            "score": opportunity.total_score, "grade": opportunity.grade,
            "pain_score": opportunity.pain_score, "intent_score": opportunity.intent_score,
            "evidence_score": opportunity.evidence_score,
        } if opportunity else None,
        "evidences": evidences,
        "statement_board": facts,  # 【事实】【AI推断】【待验证】三分看板
        "contacts": usable_contacts,
        "no_contact_note": None if usable_contacts else "未找到可用公开联系人（真实状态）；请人工查找官网联系方式并录入，不得生成猜测邮箱",
        "outreach_draft": draft,
        "validation_questions": (opportunity.validation_questions if opportunity else []) or [],
        "risk_notes": (opportunity.risk_notes if opportunity else []) or [],
        "target_status": target.status,
    }


def build_outreach_draft(
    db: Session,
    target: ExperimentTarget,
    company: Company | None,
    opportunity: Opportunity | None,
    facts: list[dict],
) -> dict:
    """话术草稿：只引用真实 Signal，绝不虚构个性化内容；仅草稿，人工修改后自行发送。"""
    real_signal_line = ""
    for item in facts:
        if item["kind"] == FACT:
            real_signal_line = item["statement"]
            break
    if not real_signal_line:
        real_signal_line = f"关注到贵司公开信息（{company.company_name if company else '企业'}）"

    value_line = (opportunity.value_proposition if opportunity else "") or "帮助业务团队减少重复性人工工作"
    company_name = company.company_name if company else "贵司"
    subject = f"关于{company_name}的一个低门槛验证邀请"
    body = (
        f"您好（{company_name}）：\n\n"
        f"{real_signal_line}。\n\n"
        f"我们正在与几家同类企业一起验证一个方向：{value_line}。"
        f"希望能用 15~30 分钟了解贵司目前的实际做法与遇到的问题；"
        f"这一阶段我们只做调研与方案验证，不推销平台。\n\n"
        f"如果方便，是否可以约一个简短交流？\n\n"
        f"（此为系统生成的草稿，请人工核实与修改后发送；引用信息均来自公开来源）"
    )
    return {
        "channel": "EMAIL",
        "subject": subject,
        "body": body,
        "generated_by": "RULE_TEMPLATE_V1",
        "is_draft_only": True,
        "warning": "草稿仅基于真实公开信号生成，未自动发送；禁止添加未经证实的个性化内容（如融资/营收增长）",
    }


def build_experiment_report(db: Session, experiment_id: str) -> dict:
    """实验报告：【真实结果】全部来自数据库；【系统分析】只是统计描述（任务书五十五/五十六）。"""
    from app.models.experiment import Experiment

    exp = db.get(Experiment, experiment_id)
    metrics = experiment_metrics(db, experiment_id)
    funnel = experiment_funnel(db, experiment_id)
    targets = db.scalars(select(ExperimentTarget).where(ExperimentTarget.experiment_id == experiment_id)).all()

    # 拒绝原因分布（真实数据）
    outcomes = db.scalars(select(ExperimentOutcome).where(ExperimentOutcome.experiment_id == experiment_id)).all()
    reject_distribution: dict[str, int] = {}
    for o in outcomes:
        if o.reject_reason:
            reject_distribution[o.reject_reason] = reject_distribution.get(o.reject_reason, 0) + 1

    # 回复分类分布（真实 REPLY 互动的 result）
    interactions = db.scalars(select(Interaction).where(Interaction.experiment_id == experiment_id)).all()
    reply_distribution: dict[str, int] = {}
    for i in interactions:
        if i.interaction_type == "REPLY" and i.result:
            reply_distribution[i.result] = reply_distribution.get(i.result, 0) + 1

    # 机会分数分桶 vs 真实回复（Opportunity 质量指标，任务书四十九）
    score_buckets: dict[str, dict] = {}
    for t in targets:
        opp = db.get(Opportunity, t.opportunity_id) if t.opportunity_id else None
        if not opp:
            continue
        bucket = f"{int(opp.total_score // 10) * 10}-{int(opp.total_score // 10) * 10 + 9}"
        b = score_buckets.setdefault(bucket, {"count": 0, "replied": 0, "met": 0})
        b["count"] += 1
        if t.reached_stage and TARGET_RANK.get(t.reached_stage, 0) >= TARGET_RANK.get("REPLIED", 4):
            b["replied"] += 1
        if t.reached_stage and TARGET_RANK.get(t.reached_stage, 0) >= TARGET_RANK.get("MEETING", 6):
            b["met"] += 1

    analysis_lines = [
        f"共 {funnel['targets']} 家目标企业，联系 {funnel['contacted']} 家，回复 {funnel['replied']} 家。",
        f"拒绝原因分布：{reject_distribution or '暂无'}；回复分类分布：{reply_distribution or '暂无'}。",
        "样本量达到 10+ 前不建议据此修改评分模型（任务书四十六）。",
    ]

    return {
        "experiment": {"id": exp.id, "name": exp.name, "status": exp.status, "conclusion": exp.conclusion} if exp else None,
        "snapshot": exp.snapshot_json if exp else {},
        "real_results": {
            "metrics": metrics,
            "funnel": funnel,
            "reject_reason_distribution": reject_distribution,
            "reply_category_distribution": reply_distribution,
            "opportunity_score_buckets": score_buckets,
        },
        "system_analysis": {
            "label": "系统分析（只读统计描述，不修改任何真实结果）",
            "lines": analysis_lines,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


TARGET_RANK = {"NEW": 0, "RESEARCHING": 1, "READY_TO_CONTACT": 2, "CONTACTED": 3, "REPLIED": 4,
               "QUALIFIED": 5, "MEETING": 6, "QUOTED": 7, "PILOT": 8, "WON": 9,
               "REJECTED": 3, "NO_RESPONSE": 3, "PAUSED": 2}


def export_targets_csv(db: Session, experiment_id: str) -> io.StringIO:
    """实验目标导出 CSV（任务书五十七）。"""
    targets = db.scalars(select(ExperimentTarget).where(ExperimentTarget.experiment_id == experiment_id)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "company", "opportunity_score", "grade", "signal_types", "evidence_score",
        "contact_status", "reached_stage", "reply", "meeting", "quote", "outcome", "reject_reason",
        "selection_reason",
    ])
    for t in targets:
        company = db.get(Company, t.company_id)
        opp = db.get(Opportunity, t.opportunity_id) if t.opportunity_id else None
        interactions = db.scalars(select(Interaction).where(Interaction.target_id == t.id)).all()
        signal_types = []
        evidence_score = None
        if opp:
            rows = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opp.id)).all()
            for r in rows:
                sig = db.get(Signal, r.signal_id) if r.signal_id else None
                if sig and sig.signal_type not in signal_types:
                    signal_types.append(sig.signal_type)
            evidence_score = opp.evidence_score
        outcome = db.scalar(select(ExperimentOutcome).where(ExperimentOutcome.target_id == t.id))
        reached = TARGET_RANK.get(t.reached_stage, 0)
        writer.writerow([
            company.company_name if company else t.company_id,
            opp.total_score if opp else None,
            opp.grade if opp else None,
            "|".join(signal_types),
            evidence_score,
            t.status,
            t.reached_stage,
            "Y" if reached >= TARGET_RANK["REPLIED"] else "",
            "Y" if reached >= TARGET_RANK["MEETING"] else "",
            "Y" if reached >= TARGET_RANK["QUOTED"] else "",
            outcome.final_status if outcome else "",
            outcome.reject_reason if outcome else "",
            "; ".join(t.selection_reason or []),
        ])
    buffer.seek(0)
    return buffer
