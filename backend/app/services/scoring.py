from dataclasses import dataclass
from math import prod


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


def _clamp(value: int | float) -> float:
    return max(0.0, min(float(value), 100.0))


def grade_for_score(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def calculate_opportunity_score(data: OpportunityScoreInput) -> OpportunityScoreResult:
    values = {
        "pain": _clamp(data.pain),
        "budget": _clamp(data.budget),
        "intent": _clamp(data.intent),
        "urgency": _clamp(data.urgency),
        "agent_fit": _clamp(data.agent_fit),
        "reachability": _clamp(data.reachability),
        "evidence": _clamp(data.evidence),
    }
    score = round(
        values["pain"] * 0.25
        + values["budget"] * 0.20
        + values["intent"] * 0.20
        + values["urgency"] * 0.10
        + values["agent_fit"] * 0.10
        + values["reachability"] * 0.05
        + values["evidence"] * 0.10,
        2,
    )
    grade = grade_for_score(score)

    # Evidence gate: weak evidence can never be presented as A/S opportunity.
    if values["evidence"] < 60 and grade in {"S", "A"}:
        grade = "B"
    return OpportunityScoreResult(score=score, grade=grade)


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
