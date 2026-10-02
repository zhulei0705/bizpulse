"""ScoreEngine（T05 升级）测试：可配置权重、score_breakdown、Evidence Gate 封顶与原因。"""
from app.core.config import settings
from app.services.scoring import OpportunityScoreInput, calculate_opportunity_score, grade_for_score


def test_breakdown_contains_all_components_with_reasons():
    result = calculate_opportunity_score(
        OpportunityScoreInput(pain=80, budget=60, intent=70, urgency=50, agent_fit=90, reachability=40, evidence=80),
        reasons={"pain": ["基于3条招聘信号推断"], "evidence": ["A级官网原文"]},
    )
    assert set(result.breakdown) >= {"pain", "budget", "intent", "urgency", "agent_fit", "reachability", "evidence", "weights"}
    assert result.breakdown["pain"]["score"] == 80
    assert result.breakdown["pain"]["weight"] == 0.25
    assert result.breakdown["pain"]["weighted"] == 20
    assert "基于3条招聘信号推断" in result.breakdown["pain"]["reasons"]
    assert result.breakdown["evidence"]["reasons"] == ["A级官网原文"]


def test_weights_come_from_config():
    """权重来自配置（task spec: 25/20/20/10/10/5/10），不是散落硬编码。"""
    assert settings.opportunity_score_weights == {
        "pain": 0.25, "budget": 0.20, "intent": 0.20, "urgency": 0.10,
        "agent_fit": 0.10, "reachability": 0.05, "evidence": 0.10,
    }
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=100, budget=100, intent=100, urgency=100, agent_fit=100, reachability=100, evidence=100,
    ))
    assert result.score == 100.0


def test_grade_cap_reason_low_evidence():
    """关键测试6：Evidence Score < 60，即使 raw score=95，最终 Grade 不能超过 B。"""
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=100, budget=100, intent=100, urgency=90, agent_fit=100, reachability=80, evidence=45,
    ))
    assert result.score >= 90  # raw 总分高于 90
    assert result.grade == "B"
    assert result.grade_cap_reason == "LOW_EVIDENCE"


def test_no_cap_with_strong_evidence():
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=100, budget=100, intent=100, urgency=90, agent_fit=100, reachability=80, evidence=85,
    ))
    assert result.grade == "S"
    assert result.grade_cap_reason is None


def test_grade_thresholds_from_config():
    assert grade_for_score(93) == "S"
    assert grade_for_score(85) == "A"
    assert grade_for_score(75) == "B"
    assert grade_for_score(65) == "C"
    assert grade_for_score(50) == "D"
