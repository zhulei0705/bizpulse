"""EvidenceAnalyzer —— 证据评分与矛盾证据（T05）。

Evidence Score 考虑：数量、来源等级、多来源一致性、新鲜度、原文明确程度、企业关联可靠度；
矛盾证据（CONTRADICTING）必须在评分中体现 —— BizPulse 不只告诉用户为什么值得买，
也必须告诉为什么可能不值得。

矛盾识别为规则驱动、可解释：支持类信号与官方否定性表述同时出现时降分并记录。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.analyzers.opportunity.context import CompanyAnalysisContext, SignalContext
from app.core.constants import EVIDENCE_POLARITY

# 矛盾证据规则：signal_type + 否定性原文模式（原文可寻，可审计）
_CONTRADICTION_RULES: list[dict] = [
    {"signal_types": {"SALES_HIRING", "HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING", "AI_HIRING"},
     "pattern": re.compile(r"(暂停|冻结|放缓|取消).{0,10}(招聘|扩招|社招|校招|hiring)", re.I),
     "note": "存在招聘信号，但原文出现暂停/冻结招聘的表述"},
    {"signal_types": {"OVERSEAS_EXPANSION", "EXPANSION", "NEW_MARKET"},
     "pattern": re.compile(r"(暂停|放缓|推迟|终止|退出|收缩).{0,14}(海外|扩张|国际|出海|新市场)", re.I),
     "note": "存在扩张信号，但原文出现暂停/收缩扩张的表述"},
    {"signal_types": {"FUNDING"},
     "pattern": re.compile(r"(裁员|缩编|优化人员|降本节流|资金链)", re.I),
     "note": "存在融资信号，但原文出现裁员/资金紧张的表述"},
    {"signal_types": {"AI_TRANSFORMATION", "AI_DEMAND", "DIGITAL_TRANSFORMATION", "AUTOMATION_DEMAND"},
     "pattern": re.compile(r"(暂停|搁置|否决|取消).{0,12}(AI|人工智能|数字化|智能化|信息化)", re.I),
     "note": "存在 AI/数字化信号，但原文出现暂停/搁置相关项目的表述"},
    {"signal_types": {"PROCUREMENT", "TENDER"},
     "pattern": re.compile(r"(终止|取消|废标|流标|撤回).{0,8}(采购|招标|项目)", re.I),
     "note": "存在采购信号，但原文出现终止/取消采购的表述"},
]

_GRADE_SCORE = {"A": 100, "B": 80, "C": 60, "D": 40}


@dataclass
class EvidenceRef:
    signal_id: str
    source_record_id: str | None
    polarity: str  # SUPPORTING / NEUTRAL / CONTRADICTING
    grade: str
    excerpt: str
    url: str | None = None
    published_at: str | None = None


@dataclass
class EvidenceResult:
    score: int
    refs: list[EvidenceRef] = field(default_factory=list)
    contradicting: list[EvidenceRef] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def detect_contradicting(ctx: CompanyAnalysisContext) -> list[dict]:
    """规则识别矛盾证据：返回 [{signal_id, source_record_id, pattern_note, excerpt}]。

    只在 SignalEvidence 原文摘录与其来源记录正文中匹配，全部可回溯原文。
    """
    found: list[dict] = []
    seen: set[str] = set()
    for sc in ctx.signals:
        rule = next((r for r in _CONTRADICTION_RULES if sc.signal.signal_type in r["signal_types"]), None)
        if rule is None:
            continue
        texts = [(e.quoted_text or "", e.source_record_id) for e in sc.evidences]
        if sc.record is not None:
            texts.append((sc.record.raw_text or "", sc.record.id))
        for text, record_id in texts:
            match = rule["pattern"].search(text)
            if not match:
                continue
            start = max(0, match.start() - 40)
            excerpt = re.sub(r"\s+", " ", text[start:match.end() + 60]).strip()
            key = f"{sc.signal.id}:{record_id}:{match.group(0)}"
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "signal_id": sc.signal.id,
                "signal_type": sc.signal.signal_type,
                "source_record_id": record_id,
                "note": rule["note"],
                "excerpt": excerpt[:300],
            })
    return found


def compute_evidence_score(ctx: CompanyAnalysisContext, *, now: datetime | None = None) -> EvidenceResult:
    now = now or datetime.now(timezone.utc)
    refs: list[EvidenceRef] = []
    times: list[datetime] = []
    for sc in ctx.signals:
        for evidence in sc.evidences:
            record = sc.record
            url = getattr(record, "url", None) if record is not None else None
            published = getattr(record, "published_at", None) if record is not None else None
            refs.append(EvidenceRef(
                signal_id=sc.signal.id,
                source_record_id=evidence.source_record_id or (record.id if record else None),
                polarity="SUPPORTING",
                grade=sc.source_grade,
                excerpt=(evidence.quoted_text or "")[:300],
                url=url,
                published_at=(published.isoformat() if published else None),
            ))
            if published:
                times.append(_ensure_utc(published))
            if evidence.created_at:
                times.append(_ensure_utc(evidence.created_at))

    reasons: list[str] = []
    count = len(refs)

    # 5→0) 矛盾证据先识别：无证据时也要返回记录
    contradictions = detect_contradicting(ctx)
    contradiction_refs: list[EvidenceRef] = []
    for item in contradictions:
        record_id = item.get("source_record_id")
        ref = EvidenceRef(
            signal_id=item["signal_id"],
            source_record_id=record_id if isinstance(record_id, str) else None,
            polarity="CONTRADICTING",
            grade=next((sc.source_grade for sc in ctx.signals if sc.signal.id == item["signal_id"]), "C"),
            excerpt=item["excerpt"],
        )
        contradiction_refs.append(ref)

    # 1) 数量：单条弱证据不足以支撑高等级机会；无证据 → 直接 0 分（Gate 层另有硬拦截）
    if count == 0:
        return EvidenceResult(score=0, refs=[], contradicting=contradiction_refs,
                              reasons=["无任何原文证据（Evidence Count = 0）"])
    if count == 1:
        count_score = 40
        reasons.append("仅 1 条证据（不足，需要多来源印证）")
    elif count == 2:
        count_score = 60
        reasons.append("2 条证据")
    elif count == 3:
        count_score = 75
        reasons.append("3 条证据")
    else:
        count_score = 85
        reasons.append(f"{count} 条证据（多来源）")

    # 2) 来源等级：A 级高权重，D 级转载不得成为强证据
    grades = [r.grade for r in refs]
    best = min(grades, key=lambda g: _GRADE_SCORE.get(g, 40)) if grades else "D"
    grade_score = _GRADE_SCORE.get(best, 40)
    if count:
        reasons.append(f"最高来源等级 {best}")
        if count >= 2 and len(set(r.source_record_id for r in refs)) >= 2:
            grade_score = min(100, grade_score + 8)
            reasons.append("多来源相互印证（+8）")

    # 3) 新鲜度：最新证据越新越高（发布时间或采集时间）
    freshness_score = 50
    if times:
        age_days = (now - max(times)).days
        freshness_score = 90 if age_days <= 7 else (75 if age_days <= 30 else (55 if age_days <= 90 else 30))
        reasons.append(f"最新证据 {age_days} 天前")
    else:
        reasons.append("证据无明确发布时间（按采集时间默认中性）")

    # 4) 原文明确程度：含数字/具体动作
    explicit = 0
    if refs:
        sample = " ".join(r.excerpt for r in refs)
        explicit = 55
        if re.search(r"\d", sample):
            explicit += 15
        if re.search(r"(招聘|采购|招标|融资|发布|扩张|签约|上线|中标)", sample):
            explicit += 15
        if max(len(r.excerpt) for r in refs) >= 60:
            explicit += 10
        explicit = min(explicit, 100)

    # 4) 矛盾证据：每条 -18，记录并写风险
    penalty = 18 * len(contradiction_refs)

    raw = count_score * 0.40 + grade_score * 0.25 + freshness_score * 0.20 + explicit * 0.15
    score = int(round(max(0, min(raw - penalty, 100))))

    if contradiction_refs:
        reasons.append(f"发现 {len(contradiction_refs)} 条矛盾证据（每条 -18）：{contradiction_refs[0].excerpt[:60]}")
    return EvidenceResult(score=score, refs=refs, contradicting=contradiction_refs, reasons=reasons)


def polarity_label(polarity: str) -> str:
    return EVIDENCE_POLARITY.get(polarity, polarity)
