"""BudgetAnalyzer —— 预算能力评分（T05）。

只能根据可验证代理信号判断：公开采购预算/招标金额/明确项目预算/企业规模/
公开融资/持续招聘投入/已有相关软件投入。金额只能从真实 Evidence 原文中提取，
提取不到 → budget_level=UNKNOWN，禁止 AI 生成预算金额。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers.opportunity.context import CompanyAnalysisContext
from app.models.signal import Signal, SignalEvidence

# 金额提取：只允许"数字 + 单位"出现在采购/预算语境，且必须能在原文找到
# （兼容 ￥/¥/人民币 前缀，如"预算金额 ￥400万元"）
_AMOUNT_PATTERN = re.compile(
    r"(预算|金额|投资额|标的|总投资|项目金额)[:：]?\s*(?:[￥¥]|人民币)?\s*([0-9]+(?:\.[0-9]+)?)\s*(亿元|万元|亿|万|美元|万美元|元)"
)
_PROCUREMENT_CONTEXT = re.compile(r"(采购|招标|投标|中标|预算|询价|标的)", re.I)


@dataclass
class BudgetResult:
    score: int
    budget_level: str  # UNKNOWN / LOW / MEDIUM / HIGH
    reasons: list[str] = field(default_factory=list)
    amounts: list[dict] = field(default_factory=list)  # 从原文提取的金额（带来源引用）


def _to_wan(value: float, unit: str) -> float:
    if unit in {"亿元", "亿"}:
        return value * 10000
    if unit in {"万元", "万"}:
        return value
    if unit == "万美元":
        return value * 7  # 标注为估算换算，仅用于分档，不作为事实输出
    if unit == "美元":
        return value * 7 / 10000
    return value / 10000  # 元


def _level_for_score(score: int, *, has_direct_evidence: bool) -> str:
    """预算等级：没有公开金额/融资等直接证据时保持 UNKNOWN（信息不足 → 中性，不猜测）。"""
    if not has_direct_evidence:
        return "UNKNOWN"
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "LOW"
    return "UNKNOWN"


def compute_budget(ctx: CompanyAnalysisContext, db: Session, *, now: datetime | None = None) -> BudgetResult:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    amounts: list[dict] = []
    types = ctx.signal_types
    score = 0

    # 1) 真实原文中的公开采购/招标金额（最强预算证据）
    #    扫描范围：信号证据摘录 + 采购/招标类信号的来源记录完整原文（均为真实原文，金额带来源引用可回溯）
    procurement_signals = [s for s in ctx.signals if s.signal.signal_type in {"PROCUREMENT", "TENDER", "SUPPLIER_SEARCH"}]
    scanned_texts: list[tuple[str, str, str | None]] = []  # (text, signal_id, record_id)
    for sc in procurement_signals:
        for evidence in sc.evidences:
            scanned_texts.append((evidence.quoted_text or "", sc.signal.id, sc.signal.source_record_id))
        if (sc.signal.fact_summary or "") and sc.signal.fact_summary not in ("", None):
            scanned_texts.append((sc.signal.fact_summary, sc.signal.id, sc.signal.source_record_id))
        raw = getattr(sc.record, "raw_text", None) if sc.record is not None else None
        if raw:
            scanned_texts.append((raw, sc.signal.id, getattr(sc.record, "id", None)))
    for text, signal_id, record_id in scanned_texts:
        if not text or not _PROCUREMENT_CONTEXT.search(text):
            continue
        for match in _AMOUNT_PATTERN.finditer(text):
            try:
                value = float(match.group(2))
            except ValueError:
                continue
            unit = match.group(3)
            wan = _to_wan(value, unit)
            amounts.append({
                "raw": match.group(0).strip()[:80],
                "amount_wan": wan,
                "signal_id": signal_id,
                "source_record_id": record_id,
                "note": "金额来自真实原文摘录（原文可回溯），仅当原文明确时提取",
            })
    # 同记录同金额去重
    seen_amounts: set[tuple] = set()
    unique_amounts: list[dict] = []
    for item in amounts:
        key = (item["source_record_id"], item["raw"])
        if key in seen_amounts:
            continue
        seen_amounts.add(key)
        unique_amounts.append(item)
    amounts = unique_amounts
    if amounts:
        best = max(a["amount_wan"] for a in amounts)
        if best >= 1000:
            score = 95
        elif best >= 100:
            score = 85
        elif best >= 50:
            score = 75
        elif best >= 10:
            score = 65
        else:
            score = 55
        reasons.append(f"原文明确预算/金额（最大约 {best:g} 万）：{'、'.join(a['raw'] for a in amounts[:3])}")

    # 2) 公开融资（90 天内）
    if "FUNDING" in types:
        funding = next(s for s in ctx.signals if s.signal.signal_type == "FUNDING")
        anchor = funding.newest_evidence_at or funding.signal.collected_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if now - anchor <= timedelta(days=90):
            score = max(score, 65)
            reasons.append("90 天内有公开融资事件（扩张资金能力代理信号）")
        else:
            score = max(score, 50)
            reasons.append("存在公开融资事件（超过 90 天）")

    # 3) 企业规模（真实 employee_range 字段，Unknown 不补充）—— 弱代理信号，仅小幅参考
    er = ctx.company.employee_range
    if er:
        size_score = 40
        try:
            upper = int(re.sub(r"[^\d]", "", er.split("-")[-1] or "0") or 0)
        except ValueError:
            upper = 0
        if upper >= 1000 or "10000" in er or ("以上" in er and upper >= 1000):
            size_score = 65
        elif upper >= 100:
            size_score = 45
        score = max(score, size_score)
        reasons.append(f"企业规模（真实标注）：{er}")

    # 4) 持续招聘投入（多类招聘信号 = 人力投入意愿）
    hiring = [t for t in types if t.endswith("_HIRING") or t == "HIRING"]
    if len(hiring) >= 2:
        score = max(score, 55)
        reasons.append(f"多团队招聘投入：{'、'.join(hiring)}")
    elif hiring:
        score = max(score, 45)
        reasons.append(f"存在招聘投入信号：{'、'.join(hiring)}")

    if score == 0:
        reasons.append("无预算相关可验证信号 → Budget 保持 UNKNOWN，不猜测金额")

    has_direct = bool(amounts) or "FUNDING" in types
    if not has_direct:
        reasons.append("无公开金额/融资等直接预算证据 → budget_level=UNKNOWN（不猜测金额）")
    return BudgetResult(
        score=max(0, min(score, 100)),
        budget_level=_level_for_score(score, has_direct_evidence=has_direct),
        reasons=reasons,
        amounts=amounts,
    )
