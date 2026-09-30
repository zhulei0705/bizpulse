"""机会评分引擎单元测试：权重、等级、证据门槛（Evidence<60 最高 B）。"""
from app.services.scoring import OpportunityScoreInput, calculate_opportunity_score, grade_for_score


def test_score_weights_follow_spec():
    # Pain25% Budget20% Intent20% Urgency10% AgentFit10% Reachability5% Evidence10%
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=80, budget=60, intent=70, urgency=50, agent_fit=90, reachability=40, evidence=80,
    ))
    expected = round(80 * 0.25 + 60 * 0.20 + 70 * 0.20 + 50 * 0.10 + 90 * 0.10 + 40 * 0.05 + 80 * 0.10, 2)
    assert result.score == expected  # 21.5+18+14+5+9+2+8 = 71.5


def test_grade_boundaries():
    assert grade_for_score(90) == "S"
    assert grade_for_score(89.99) == "A"
    assert grade_for_score(80) == "A"
    assert grade_for_score(79.99) == "B"
    assert grade_for_score(70) == "B"
    assert grade_for_score(60) == "C"
    assert grade_for_score(59.99) == "D"


def test_evidence_gate_caps_at_b():
    # 总分 83 足够 A 级，但 evidence=40 < 60，最高只能 B
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=90, budget=90, intent=90, urgency=80, agent_fit=90, reachability=70, evidence=40,
    ))
    assert result.score == 83.0
    assert result.grade == "B"


def test_evidence_gate_does_not_lower_below_b():
    # evidence=0 时总分被拉低，等级按实际分数计算，不额外降级
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=100, budget=100, intent=100, urgency=100, agent_fit=100, reachability=100, evidence=0,
    ))
    assert result.score == 90.0
    assert result.grade == "B"


def test_strong_evidence_allows_s():
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=100, budget=100, intent=100, urgency=100, agent_fit=100, reachability=100, evidence=100,
    ))
    assert result.score == 100.0
    assert result.grade == "S"


def test_scores_are_clamped():
    result = calculate_opportunity_score(OpportunityScoreInput(
        pain=150, budget=-20, intent=100, urgency=100, agent_fit=100, reachability=100, evidence=100,
    ))
    # pain clamp 到 100，budget clamp 到 0
    assert result.score == round(100 * 0.25 + 0 * 0.20 + 100 * 0.20 + 100 * 0.10 + 100 * 0.10 + 100 * 0.05 + 100 * 0.10, 2)
