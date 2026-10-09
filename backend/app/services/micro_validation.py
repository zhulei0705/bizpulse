"""T09 微型验证 Sprint 服务：候选排序 / Contact Role Fit / Offer 评分 / 草稿事实校验。

原则（T09 任务书四/十/十一/十三/十六）：
- 排序组成全部来自已有真实数据，权重固定可解释，不用 LLM 打分；
- Offer Score 7 维结构化评分，AI 只解释不伪造购买意愿；
- role_fit 只依据公开职位/部门/邮箱功能标注，无依据 → UNKNOWN；
- 触达草稿中每条事实性陈述必须能映射到 Evidence/SourceRecord 原文，否则删除。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.signal import Signal, SignalEvidence
from app.services.actionability import compute_signal_actionability

# 任务书四：Micro Validation Candidate Ranking 权重
RANKING_WEIGHTS = {
    "actionability": 0.30,
    "pain_strength": 0.20,
    "intent": 0.15,
    "evidence": 0.15,
    "reachability": 0.10,
    "solution_fit": 0.10,
}

ROLE_FIT_LEVELS = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")

# 功能性邮箱前缀 → 业务角色（公开可校验的规则）
_SALES_PREFIX = ("sales", "sale", "market", "bd", "business", "coop", "partner", "xiaoshou")
_HR_PREFIX = ("hr", "job", "career", "recruit", "zhaopin", "renshi")
_SERVICE_PREFIX = ("service", "support", "kf", "cs", "after")
_PRESS_PREFIX = ("press", "media", "pr")


def contact_role_fit(contact: CompanyContact, *, label_basis: str | None = None) -> str:
    """联系人角色匹配度（对'向该企业卖东西'而言）。规则依据公开字段：
    - 具名联系人（name）且 contact_type ∈ {SALES, BUSINESS, PROCUREMENT} → HIGH；
    - 本企业域名的商务功能邮箱（前缀规则）或 contact_type SALES/BUSINESS → MEDIUM；
    - HR/客服/媒体邮箱、纯总机电话 → LOW（只证明可触达，不当决策人，任务书二十一）；
    - 官方表单 → UNKNOWN（无依据判断谁在看）；
    - 其他 → UNKNOWN。
    label_basis：来源页公开的功能标注（如"国内业务邮箱"）可把 UNKNOWN 提升到 MEDIUM。
    """
    has_name = bool(contact.name)
    ctype = (contact.contact_type or "").upper()
    email = (contact.email or "").lower()
    local = email.split("@", 1)[0] if email else ""

    if ctype in {"SALES", "BUSINESS", "PROCUREMENT"} and has_name:
        return "HIGH"
    if ctype in {"SALES", "BUSINESS"}:
        return "MEDIUM"
    if email and any(local.startswith(p) for p in _SALES_PREFIX):
        return "MEDIUM"
    if email and label_basis and any(k in label_basis for k in ("业务邮箱", "商务邮箱", "销售邮箱", "合作邮箱")):
        return "MEDIUM"  # 来源页对该邮箱的功能标注（仅作用于邮箱，不得提升电话/表单）
    if ctype == "HR" or any(local.startswith(p) for p in _HR_PREFIX):
        return "LOW"
    if ctype == "CUSTOMER_SERVICE" or any(local.startswith(p) for p in _SERVICE_PREFIX):
        return "LOW"
    if any(local.startswith(p) for p in _PRESS_PREFIX):
        return "LOW"
    if contact.phone and not email and not contact.public_profile_url:
        return "LOW"  # 纯总机
    if contact.public_profile_url and not email and not phone_of(contact):
        return "UNKNOWN"  # 表单
    return "UNKNOWN"


def phone_of(contact: CompanyContact) -> str | None:
    return contact.phone


def contact_channel(contact: CompanyContact) -> str:
    if contact.email:
        return "EMAIL"
    if contact.phone:
        return "PHONE"
    if contact.public_profile_url:
        return "WEBSITE_FORM"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# 候选排序（任务书四）
# ---------------------------------------------------------------------------

def rank_micro_candidates(db: Session, candidates: list[dict]) -> list[dict]:
    """对已通过硬筛（COMPANY + Approved ACTIONABLE_NOW + 证据真实 + URL有效 + 新鲜）的候选打分排序。

    每个 candidate 需携带真实数据字段：
      actionability_sub(0-100), pain_sub, intent_sub, evidence_sub, reachability_sub, solution_fit_sub
    这些子分由调用方从 Opportunity/Signal/Contact 真实数据读取（见 prepare_sprint.py）。
    """
    ranked = []
    for c in candidates:
        score = round(sum(c["subs"][k] * RANKING_WEIGHTS[k] for k in RANKING_WEIGHTS), 2)
        ranked.append({**c, "ranking_score": score})
    ranked.sort(key=lambda x: -x["ranking_score"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


# ---------------------------------------------------------------------------
# Offer Score（任务书十）：7 维结构化评分，0~100
# ---------------------------------------------------------------------------

OFFER_SCORE_DIMS = (
    "pain_match", "urgency", "measurability", "delivery_feasibility",
    "time_to_value", "buyer_clarity", "revenue_likelihood",
)


def score_offer(offer: dict) -> dict:
    """Offer 结构化评分。输入为结构化字段（真实数据/明确标注的人工判断），代码合成。
    - pain_match: 与已批准信号的 Pain 假设直接对应 → 高；间接 → 中
    - urgency: 信号新鲜度（有明确近期日期 → 高；仅"官网当前展示" → 中；无 → 低）
    - measurability: success_metric 可量化 → 高
    - delivery_feasibility: 试点所需数据能力是否为系统已有能力
    - time_to_value: 试点时长 ≤14 天 → 高
    - buyer_clarity: 由 role_fit 映射（HIGH 90 / MEDIUM 70 / LOW 40 / UNKNOWN 25）
    - revenue_likelihood: 价值属四类之一且有 price_hypothesis → 中高
    """
    sub = {
        "pain_match": offer.get("pain_match_score", 50),
        "urgency": offer.get("urgency_score", 50),
        "measurability": 85 if offer.get("success_metric") else 35,
        "delivery_feasibility": offer.get("delivery_feasibility_score", 60),
        "time_to_value": 85 if int(offer.get("pilot_duration_days", 30)) <= 14 else (60 if int(offer.get("pilot_duration_days", 30)) <= 30 else 30),
        "buyer_clarity": {"HIGH": 90, "MEDIUM": 70, "LOW": 40, "UNKNOWN": 25}[offer.get("buyer_clarity", "UNKNOWN")],
        "revenue_likelihood": 65 if (offer.get("price_hypothesis") and offer.get("value_type") in {"增加收入", "降低成本", "节省时间", "降低风险"}) else 30,
    }
    total = round(sum(sub.values()) / len(sub.values()), 1)
    return {"dims": sub, "total": total}


# ---------------------------------------------------------------------------
# 草稿事实校验（任务书十六）
# ---------------------------------------------------------------------------

def factcheck_claims(db: Session, claims: list[dict]) -> list[dict]:
    """每条事实性陈述必须映射到 Evidence：quoted_text 必须是指定 SourceRecord 原文的精确子串。

    claim 结构：{claim, quote, source_record_id}
    返回逐条 PASS/FAIL；任何 FAIL → 草稿不得进入 READY_FOR_MANUAL_OUTREACH。
    """
    results = []
    for claim in claims:
        record_raw = None
        if claim.get("source_record_id"):
            from app.models.source import SourceRecord

            record = db.get(SourceRecord, claim["source_record_id"])
            record_raw = (record.raw_text if record else "") or ""
        quote = claim.get("quote") or ""
        ok = bool(record_raw) and bool(quote) and quote in record_raw
        results.append({
            "claim": claim.get("claim"),
            "quote": quote[:80],
            "source_record_id": claim.get("source_record_id"),
            "pass": ok,
        })
    return results


# ---------------------------------------------------------------------------
# 候选硬筛（任务书三/五）
# ---------------------------------------------------------------------------

def screen_candidates(db: Session, *, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """从正式库硬筛：COMPANY + Approved ACTIONABLE_NOW 信号 + Evidence 真实 + URL 有效。

    返回 (passed, excluded)。excluded 带原因（新鲜度不足/纯宣传/历史信号等由调用方补充人工判断）。
    新鲜度判定：有明确发布日期 → 按"日期距今 ≤180 天或为进行中招聘类"通过；
    无日期但为进行中行为类（招聘/需求族）且官网当前展示 → 通过并标注风险；
    无日期且为一次性事件类（新设机构/新品等）→ 不通过（无法证明新鲜）。
    """
    now = now or datetime.now(timezone.utc)
    from app.services.actionability import compute_actionability_by_rules

    passed, excluded = [], []
    signals = db.scalars(select(Signal).where(Signal.status == "APPROVED")).all()
    seen_companies: dict[str, dict] = {}
    for s in signals:
        company = db.get(Company, s.company_id)
        if company is None or company.organization_type != "COMPANY":
            continue
        actionability = compute_signal_actionability(db, s)
        if actionability != "ACTIONABLE_NOW":
            excluded.append({'company': company.company_name, 'signal_type': s.signal_type, 'reason': actionability})
            continue
        evs = db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == s.id)).all()
        if not evs:
            excluded.append({"company": company.company_name, "signal_type": s.signal_type,
                             "reason": "无 SignalEvidence（证据缺失）"})
            continue
        record = s.source_record
        if record is None or record.http_status not in (200, None):
            excluded.append({"company": company.company_name, "signal_type": s.signal_type,
                             "reason": "Source URL 无效"})
            continue

        st = s.signal_type
        fresh_status = "DATED_RECENT" if s.published_at else (
            "ONGOING_UNDATED" if compute_actionability_by_rules(s) == "ACTIONABLE_NOW" and st in {
                "HIRING", "SALES_HIRING", "AI_HIRING", "TECH_HIRING", "CUSTOMER_SERVICE_HIRING",
                "FINANCE_HIRING", "SUPPLIER_SEARCH", "CRM_DEMAND", "ERP_DEMAND", "AI_DEMAND",
                "AUTOMATION_DEMAND", "DIGITAL_TRANSFORMATION", "AI_TRANSFORMATION",
            } else "UNDATED_EVENT")
        if fresh_status == "UNDATED_EVENT":
            excluded.append({"company": company.company_name, "signal_type": st,
                             "reason": "Signal 无发布日期且为一次性事件（无法证明新鲜度，任务书三）"})
            continue

        entry = seen_companies.setdefault(company.id, {
            "company_id": company.id, "company_name": company.company_name,
            "signals": [], "freshness": fresh_status,
        })
        entry["signals"].append({
            "signal_id": s.id, "signal_type": st, "confidence": s.confidence,
            "published_at": s.published_at.isoformat() if s.published_at else None,
            "evidence": evs[0].quoted_text[:160],
            "source_url": record.url,
            "source_record_id": record.id,
        })

    passed = list(seen_companies.values())
    return passed, excluded
