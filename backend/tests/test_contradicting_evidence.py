"""矛盾证据测试（T05）：支持类信号 + 官方否定表述 → 必须识别、降分、写风险。"""
from types import SimpleNamespace

from tests.helpers_t05 import make_company_context, make_signal, persist_company_with_source, persist_signal, utcnow

from app.analyzers.opportunity.evidence import compute_evidence_score, detect_contradicting


def _record(record_id: str, raw_text: str) -> SimpleNamespace:
    return SimpleNamespace(id=record_id, raw_text=raw_text, url=None, published_at=None)


def test_hiring_with_pause_statement():
    """关键测试4：SALES_HIRING + 暂停销售扩张的官方声明 → 识别矛盾，不能盲目高分。"""
    ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=85, grade="A",
                    evidence_text="公司官网发布海外销售团队招聘计划，新增5个岗位",
                    title="销售招聘"),
    ])
    # 同一来源原文中出现否定性表述
    ctx.signals[0].record = _record("rec_1", "公司官网发布海外销售团队招聘计划。不过公司官方声明：因业务调整，本季度暂停招聘扩编，放缓海外市场投入。")
    contradictions = detect_contradicting(ctx)
    assert contradictions, "必须识别出矛盾证据"
    assert any("暂停" in c["note"] or "招聘" in c["note"] for c in contradictions)
    result = compute_evidence_score(ctx)
    assert result.contradicting
    # 矛盾证据必须拉低 Evidence Score
    clean_ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=85, grade="A",
                    evidence_text="公司官网发布海外销售团队招聘计划，新增5个岗位"),
    ])
    clean_score = compute_evidence_score(clean_ctx).score
    assert result.score < clean_score


def test_expansion_with_withdrawal_statement():
    ctx = make_company_context([
        make_signal("sig_1", "OVERSEAS_EXPANSION", confidence=80, grade="B",
                    evidence_text="公司宣布进军海外市场"),
    ])
    ctx.signals[0].record = _record("rec_2", "公司此前宣布进军海外市场，最新公告显示已决定终止海外扩张计划，退出相关市场。")
    contradictions = detect_contradicting(ctx)
    assert contradictions


def test_clean_text_no_false_positive():
    ctx = make_company_context([
        make_signal("sig_1", "SALES_HIRING", confidence=85, grade="A",
                    evidence_text="公司扩大销售团队，加速海外市场扩张，招聘节奏加快"),
    ])
    ctx.signals[0].record = _record("rec_3", "公司扩大销售团队，加速海外市场扩张")
    assert detect_contradicting(ctx) == []


def test_contradictions_reach_candidate_risk_notes():
    """端到端：矛盾证据进入候选的 risk_notes 与 contradicting_evidence。"""
    from app.analyzers.opportunity.generator import analyze_company_opportunities
    from app.db.session import SessionLocal
    from app.models.opportunity_candidate import OpportunityCandidate

    db = SessionLocal()
    try:
        company, source, record = persist_company_with_source(
            db, name=f"矛盾测试企业{utcnow()}", grade="A", domain="contradict-test.com")
        record.raw_text = ("公司官网发布海外销售团队招聘计划，新增5个岗位。"
                           "不过公司官方声明：因业务调整，本季度暂停招聘扩编。")
        persist_signal(db, company, source, record, "SALES_HIRING", confidence=85,
                       evidence_text="公司官网发布海外销售团队招聘计划，新增5个岗位",
                       fingerprint=f"fp_c_{company.id}", age_days=1)
        db.commit()
        stats = analyze_company_opportunities(db, company.id, force=True)
        assert stats.status == "ANALYZED"
        candidates = db.query(OpportunityCandidate).filter_by(company_id=company.id).all()
        assert candidates
        joined_risk = " ".join(sum([c.risk_notes for c in candidates], []))
        assert "矛盾证据" in joined_risk
        assert any(c.contradicting_evidence_json for c in candidates)
    finally:
        db.close()
