from app.services.scoring import OpportunityScoreInput, calculate_opportunity_score


def test_high_score_with_strong_evidence_can_be_a_or_s():
    result = calculate_opportunity_score(OpportunityScoreInput(95, 90, 90, 90, 90, 80, 90))
    assert result.score >= 80
    assert result.grade in {"A", "S"}


def test_weak_evidence_caps_grade_at_b():
    result = calculate_opportunity_score(OpportunityScoreInput(100, 100, 100, 100, 100, 100, 30))
    assert result.score >= 80
    assert result.grade == "B"
