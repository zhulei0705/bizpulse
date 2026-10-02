"""EvidenceAnalyzer 测试：数量/来源等级/一致性/新鲜度、D 级不得成为强证据、矛盾证据扣分。"""
from tests.helpers_t05 import make_company_context, make_signal

from app.analyzers.opportunity.evidence import compute_evidence_score, detect_contradicting


def test_zero_evidence_zero_score():
    ctx = make_company_context([make_signal("sig_1", "NEW_PRODUCT", confidence=60, grade="C")])
    ctx.signals[0].evidences = []
    result = compute_evidence_score(ctx)
    assert result.score == 0
    assert not result.refs


def test_multi_source_corroboration_beats_single():
    single = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="B", evidence_text="招聘海外销售5名", age_days=3),
    ])
    multi = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="B", evidence_text="招聘海外销售5名", age_days=3),
        make_signal("sig_2", "OVERSEAS_EXPANSION", confidence=78, grade="B", evidence_text="官网发布海外市场拓展公告，设立海外办事处", age_days=5),
        make_signal("sig_3", "FUNDING", confidence=85, grade="A", evidence_text="完成A轮融资5000万元", age_days=10),
    ])
    assert compute_evidence_score(multi).score > compute_evidence_score(single).score


def test_d_grade_weak():
    """一个 D 级转载不得成为强 Evidence。"""
    d_ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=60, grade="D", evidence_text="转载：某公司招聘销售", age_days=60),
    ])
    a_ctx = make_company_context([
        make_signal("sig_2", "SALES_HIRING", confidence=80, grade="A", evidence_text="官网招聘海外销售5名", age_days=3),
    ])
    assert compute_evidence_score(d_ctx).score < compute_evidence_score(a_ctx).score
    assert compute_evidence_score(d_ctx).score < 60


def test_freshness_matters():
    fresh = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="A", evidence_text="官网招聘海外销售5名", age_days=2),
    ])
    old = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="A", evidence_text="官网招聘海外销售5名", age_days=120),
    ])
    assert compute_evidence_score(fresh).score > compute_evidence_score(old).score


def test_contradicting_reduces_score_and_recorded():
    clean = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="A",
                    evidence_text="官网招聘海外销售5名", age_days=2),
    ])
    contradicted = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=80, grade="A",
                    evidence_text="官网招聘海外销售5名。但公司同时宣布暂停海外招聘，冻结扩编", age_days=2),
    ])
    clean_score = compute_evidence_score(clean).score
    result = compute_evidence_score(contradicted)
    assert result.score < clean_score
    assert result.contradicting, "矛盾证据必须被记录"


def test_refs_carry_traceability():
    ctx = make_company_context([
        make_signal("sig_1", "TENDER", confidence=85, grade="A", evidence_text="招标公告原文片段"),
    ])
    result = compute_evidence_score(ctx)
    ref = result.refs[0]
    assert ref.signal_id == "sig_1"
    assert ref.grade == "A"
    assert ref.polarity == "SUPPORTING"
    assert ref.excerpt
