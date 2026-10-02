"""OpportunityGenerator 端到端测试（关键测试1/2/5/6）：

- 无 Signal / 无 Evidence → 不产生候选；
- 弱新闻 Signal + C 级证据 → 不能生成 A 级机会，且单条弱证据 → NEED_MORE_EVIDENCE；
- 采购+预算+A 级 → Intent/Budget/Evidence 高于普通新闻候选；
- 候选 approve → 转正式 Opportunity（STAGE=REVIEW）；Evidence Count=0 → 转换被拒（422）。
"""
from tests.helpers_t05 import persist_company_with_source, persist_signal, utcnow

from app.analyzers.opportunity.generator import analyze_company_opportunities
from app.db.session import SessionLocal
from app.models.opportunity import Opportunity
from app.models.opportunity_candidate import OpportunityCandidate


def _seed(db, *, name_suffix, grade="A", signals_spec):
    company, source, record = persist_company_with_source(db, name=f"机会生成测试{name_suffix}", grade=grade)
    for i, (signal_type, confidence, evidence_text) in enumerate(signals_spec):
        persist_signal(db, company, source, record, signal_type, confidence=confidence,
                       evidence_text=evidence_text, fingerprint=f"fp_{company.id}_{i}", age_days=i + 1)
    db.commit()
    return company


def test_no_signals_skipped():
    db = SessionLocal()
    try:
        company, _, _ = persist_company_with_source(db, name=f"空信号企业{utcnow()}")
        db.commit()
        stats = analyze_company_opportunities(db, company.id)
        assert stats.status == "SKIPPED"
        assert "approved_signals" in stats.reason
    finally:
        db.close()


def test_weak_news_single_evidence_capped():
    """关键测试1：只有一条弱新闻 Signal + C 级证据 → 不能生成 A 级机会。"""
    db = SessionLocal()
    try:
        company = _seed(db, name_suffix=f"弱新闻{utcnow()}", grade="C", signals_spec=[
            ("NEW_PRODUCT", 60, "某媒体转载：该公司发布了一款新品"),
        ])
        stats = analyze_company_opportunities(db, company.id, force=True)
        assert stats.status == "ANALYZED"
        candidates = db.query(OpportunityCandidate).filter_by(company_id=company.id).all()
        assert candidates, "仍应产生候选（Lead Hint 性质）"
        for candidate in candidates:
            assert candidate.grade not in {"A", "S"}, "弱新闻不得成为 A 级机会"
            assert candidate.status == "NEED_MORE_EVIDENCE", "单条弱证据只能是 NEED_MORE_EVIDENCE"
            assert candidate.evidence_score <= 60
    finally:
        db.close()


def test_procurement_with_budget_scores_high():
    """关键测试2：公开采购 + 明确预算 + A 级政府来源 → Intent/Budget/Evidence 高于普通新闻。"""
    db = SessionLocal()
    try:
        strong = _seed(db, name_suffix=f"采购{utcnow()}", grade="A", signals_spec=[
            ("TENDER", 90, "受该单位委托发布招标公告：智能客服系统采购项目，项目预算：500万元。投标截止 2026-10-20"),
            ("PROCUREMENT", 85, "公开采购公告：客服平台采购，预算金额：500万元"),
        ])
        weak = _seed(db, name_suffix=f"新闻{utcnow()}", grade="C", signals_spec=[
            ("NEW_PRODUCT", 60, "转载新闻：某公司发布新品"),
        ])
        analyze_company_opportunities(db, strong.id, force=True)
        analyze_company_opportunities(db, weak.id, force=True)
        strong_c = db.query(OpportunityCandidate).filter_by(company_id=strong.id).all()
        weak_c = db.query(OpportunityCandidate).filter_by(company_id=weak.id).all()
        assert strong_c and weak_c
        assert max(c.intent_score for c in strong_c) > max(c.intent_score for c in weak_c) + 15
        assert max(c.budget_score for c in strong_c) > max(c.budget_score for c in weak_c) + 25
        assert max(c.evidence_score for c in strong_c) > max(c.evidence_score for c in weak_c) + 10
        assert max(c.total_score for c in strong_c) > max(c.total_score for c in weak_c)
    finally:
        db.close()


def test_candidate_explainability_fields():
    """候选必须可解释：评分明细/风险/验证问题/证据引用/why_now 齐备。"""
    db = SessionLocal()
    try:
        company = _seed(db, name_suffix=f"可解释{utcnow()}", grade="A", signals_spec=[
            ("OVERSEAS_EXPANSION", 80, "公司宣布设立海外办事处，正式拓展海外市场"),
            ("SALES_HIRING", 85, "官网招聘海外销售5名，组建海外销售团队"),
        ])
        analyze_company_opportunities(db, company.id, force=True)
        candidate = db.query(OpportunityCandidate).filter_by(company_id=company.id).order_by(OpportunityCandidate.total_score.desc()).first()
        assert candidate
        assert candidate.score_breakdown_json, "必须有 score_breakdown"
        assert "pain" in candidate.score_breakdown_json
        assert candidate.why_now, "必须有 why_now"
        assert "最近" in candidate.why_now or "天" in candidate.why_now
        assert candidate.risk_notes, "必须有 risk_notes"
        assert candidate.validation_questions, "必须有 validation_questions"
        assert candidate.evidence_refs_json, "必须有证据引用"
        assert candidate.solution_hypothesis.startswith("【SOLUTION_HYPOTHESIS】")
        assert "ROI" in candidate.value_hypothesis or "不承诺" in candidate.value_hypothesis
        # 无预算原文 → Budget UNKNOWN + 风险说明
        assert candidate.budget_score <= 60
        assert any("预算" in r for r in candidate.risk_notes)
    finally:
        db.close()


def test_approve_converts_and_zero_evidence_blocked():
    """候选 approve → 正式 Opportunity（REVIEW 待审）；Evidence Count=0 → 422 且候选标记 NEED_MORE_EVIDENCE。"""
    db = SessionLocal()
    try:
        company = _seed(db, name_suffix=f"转换{utcnow()}", grade="A", signals_spec=[
            ("TENDER", 90, "招标公告：采购智能客服系统，项目预算：500万元"),
        ])
        analyze_company_opportunities(db, company.id, force=True)
        candidate = db.query(OpportunityCandidate).filter_by(company_id=company.id).first()

        # 无证据候选（手工构造）→ 转换被拒
        import uuid
        empty = OpportunityCandidate(
            company_id=company.id, title="无证据候选", problem_hypothesis="x", solution_hypothesis="x",
            signal_ids_json=[], evidence_refs_json=[], fingerprint=f"fp_empty_{uuid.uuid4().hex[:12]}",
            total_score=50, grade="C", status="REVIEW",
        )
        db.add(empty)
        db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as client:
            # 正常转换
            resp = client.post(f"/api/v1/opportunity-candidates/{candidate.id}/approve", json={"note": "证据充分"})
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["status"] == "CONVERTED"
            opp_id = resp.json()["data"]["opportunity_id"]
            opportunity = db.get(Opportunity, opp_id)
            assert opportunity.stage == "REVIEW"
            assert opportunity.candidate_id == candidate.id
            assert opportunity.why_now
            assert opportunity.score_breakdown_json
            # Evidence Count = 0 → 阻断
            resp2 = client.post(f"/api/v1/opportunity-candidates/{empty.id}/approve", json={})
            assert resp2.status_code == 422
            db.refresh(empty)
            assert empty.status == "NEED_MORE_EVIDENCE"
    finally:
        db.close()


def test_batch_job_and_stale():
    """批量分析 job 可运行；STALE 清扫把 90 天无信号的正式机会标记过期。"""
    db = SessionLocal()
    try:
        from app.analyzers.opportunity.generator import analyze_companies_batch, mark_stale_opportunities
        from datetime import datetime, timedelta, timezone
        company = _seed(db, name_suffix=f"批量{utcnow()}", grade="A", signals_spec=[
            ("SALES_HIRING", 85, "官网招聘海外销售5名"),
        ])
        result = analyze_companies_batch(db)
        assert result["analyzed"] >= 1
        assert result["job_id"]

        # 手工把一个正式机会的 last_signal_at 推到 100 天前
        opp = db.query(Opportunity).filter_by(company_id=company.id).first()
        if opp is not None:
            opp.last_signal_at = datetime.now(timezone.utc) - timedelta(days=100)
            db.commit()
            marked = mark_stale_opportunities(db)
            db.refresh(opp)
            assert opp.stage == "STALE"
            assert opp.stale_reason
            assert marked >= 1
    finally:
        db.close()
