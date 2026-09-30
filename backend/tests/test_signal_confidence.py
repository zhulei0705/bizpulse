"""Confidence 算法测试：代码计算、权重可解释、来源等级映射、上下限。"""
from app.analyzers.confidence import compute_signal_confidence


def test_weights_sum_and_explanation():
    result = compute_signal_confidence(
        source_grade="A", evidence_text="公司招聘海外销售经理10名", evidence_in_source=True,
        rule_confidence=80, llm_confidence=85, company_resolve_status="EXACT",
    )
    assert 0 <= result.score <= 100
    exp = result.explanation
    assert abs(sum(exp["weights"].values()) - 1.0) < 1e-6  # 权重归一
    assert exp["source_score"] == 100  # A 级
    assert set(exp) == {"weights", "source_score", "evidence_clarity", "rule_confidence", "llm_score", "company_score"}


def test_high_confidence_for_strong_case():
    strong = compute_signal_confidence(
        source_grade="A", evidence_text="公司宣布完成A轮融资5000万元，用于产能扩建", evidence_in_source=True,
        rule_confidence=85, llm_confidence=90, company_resolve_status="EXACT",
    )
    weak = compute_signal_confidence(
        source_grade="D", evidence_text=None, evidence_in_source=False,
        rule_confidence=40, llm_confidence=None, company_resolve_status="UNKNOWN",
    )
    assert strong.score >= 85  # 强案例达到自动批准门槛
    assert weak.score < 50
    assert strong.score > weak.score


def test_source_grade_mapping_in_score():
    for grade, expected_source in (("A", 100), ("B", 80), ("C", 60), ("D", 40)):
        result = compute_signal_confidence(source_grade=grade, evidence_text="x" * 50, evidence_in_source=True, rule_confidence=70, llm_confidence=70, company_resolve_status="EXACT")
        assert result.explanation["source_score"] == expected_source


def test_evidence_not_in_source_lowers_clarity():
    ok = compute_signal_confidence(source_grade="A", evidence_text="招聘海外销售10名" * 5, evidence_in_source=True, rule_confidence=80, llm_confidence=80, company_resolve_status="EXACT")
    missing = compute_signal_confidence(source_grade="A", evidence_text="招聘海外销售10名" * 5, evidence_in_source=False, rule_confidence=80, llm_confidence=80, company_resolve_status="EXACT")
    assert ok.explanation["evidence_clarity"] > missing.explanation["evidence_clarity"]
    assert ok.score > missing.score


def test_llm_none_uses_neutral():
    result = compute_signal_confidence(source_grade="B", evidence_text="招聘海外销售经理10名", evidence_in_source=True, rule_confidence=75, llm_confidence=None, company_resolve_status="HIGH_CONFIDENCE")
    assert 0 <= result.score <= 100
