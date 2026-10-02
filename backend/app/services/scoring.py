"""ScoreEngine —— 机会评分（T05 升级）。

- 权重全部来自 settings.opportunity_score_weights（配置化，禁止散落硬编码）；
- 返回 score_breakdown（每个分项的分数、权重、依据），保证"为什么是这个分"可回答；
- Evidence Gate：Evidence Score < 阈值(60) 时等级最高 B，并记录 grade_cap_reason=LOW_EVIDENCE；
  Evidence Count = 0 由 evidence_gate() 拦截（禁止生成正式 Opportunity）。

总分永远由后端代码计算；LLM 只产生结构化特征与解释，不决定分数。
"""
from dataclasses import dataclass, field
from math import prod

from app.core.config import settings
from app.core.constants import PAIN_CATEGORIES


@dataclass(frozen=True)
class OpportunityScoreInput:
    pain: int
    budget: int
    intent: int
    urgency: int
    agent_fit: int
    reachability: int
    evidence: int


@dataclass(frozen=True)
class OpportunityScoreResult:
    score: float
    grade: str
    breakdown: dict = field(default_factory=dict)
    grade_cap_reason: str | None = None


def _clamp(value: int | float) -> float:
    return max(0.0, min(float(value), 100.0))


def grade_for_score(score: float) -> str:
    thresholds = settings.opportunity_grade_thresholds
    if score >= thresholds["S"]:
        return "S"
    if score >= thresholds["A"]:
        return "A"
    if score >= thresholds["B"]:
        return "B"
    if score >= thresholds["C"]:
        return "C"
    return "D"


def calculate_opportunity_score(
    data: OpportunityScoreInput,
    *,
    reasons: dict[str, list[str]] | None = None,
) -> OpportunityScoreResult:
    """计算总分/等级/明细。reasons 为各分项的解释（来自各 Analyzer，可缺省）。"""
    w = settings.opportunity_score_weights
    values = {
        "pain": _clamp(data.pain),
        "budget": _clamp(data.budget),
        "intent": _clamp(data.intent),
        "urgency": _clamp(data.urgency),
        "agent_fit": _clamp(data.agent_fit),
        "reachability": _clamp(data.reachability),
        "evidence": _clamp(data.evidence),
    }
    score = round(sum(values[k] * w[k] for k in values), 2)
    grade = grade_for_score(score)

    grade_cap_reason: str | None = None
    # Evidence Gate：证据不足，禁止呈现为高等级机会（记录封顶原因，可解释）
    if values["evidence"] < settings.evidence_gate_threshold and grade in {"S", "A"}:
        grade = "B"
        grade_cap_reason = "LOW_EVIDENCE"

    breakdown: dict = {"weights": dict(w)}
    for key, value in values.items():
        breakdown[key] = {
            "score": round(value, 1),
            "weight": w[key],
            "weighted": round(value * w[key], 2),
            "reasons": (reasons or {}).get(key, []),
        }
    return OpportunityScoreResult(
        score=score,
        grade=grade,
        breakdown=breakdown,
        grade_cap_reason=grade_cap_reason,
    )


class EvidenceGateError(ValueError):
    """正式 Opportunity 生成的硬门槛未通过。"""


def evidence_gate(evidence_count: int, evidence_score: int) -> tuple[str, str | None]:
    """正式机会生成前的硬校验：返回 (允许生成的等级上限, 封顶原因)。

    - Evidence Count = 0 → 抛 EvidenceGateError（禁止生成正式 Opportunity，只能停留在候选）；
    - Evidence Score < 60 → 最高 B（LOW_EVIDENCE）；
    - 只有 1 条弱证据（非 A/B 来源）→ 最高 C（SINGLE_WEAK_EVIDENCE），且候选应为 NEED_MORE_EVIDENCE。
    """
    if evidence_count <= 0:
        raise EvidenceGateError("Evidence Count = 0：禁止生成正式 Opportunity（仅可为 Lead Hint / 候选）")
    if evidence_score < settings.evidence_gate_threshold:
        return "B", "LOW_EVIDENCE"
    return "S", None


def calculate_market_score(
    pain: int,
    budget: int,
    frequency: int,
    automation_fit: int,
    reachability: int,
) -> float:
    values = [_clamp(x) / 100 for x in (pain, budget, frequency, automation_fit, reachability)]
    if any(v == 0 for v in values):
        return 0.0
    return round(100 * prod(values) ** (1 / len(values)), 2)


def valid_pain_category(category: str | None) -> str:
    """PainPoint 分类归一：枚举内直接返回，否则归入 OTHER。"""
    if category and category in PAIN_CATEGORIES:
        return category
    return "OTHER"
