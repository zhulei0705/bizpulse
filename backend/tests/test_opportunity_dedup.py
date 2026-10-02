"""OpportunityDeduplicator 测试：同指纹窗口内更新不新建；输入 hash 未变跳过分析。"""
from tests.helpers_t05 import persist_company_with_source, persist_signal, utcnow

from app.analyzers.opportunity.dedup import (
    compute_analysis_input_hash,
    compute_candidate_fingerprint,
)
from app.analyzers.opportunity.generator import analyze_company_opportunities
from app.db.session import SessionLocal
from app.models.opportunity_candidate import OpportunityCandidate
from app.models.source import SourceRecord


def test_fingerprint_changes_with_period():
    fp1 = compute_candidate_fingerprint("cmp1", "SALES_EFFICIENCY", "AI 销售效率工具")
    fp2 = compute_candidate_fingerprint("cmp1", "SALES_EFFICIENCY", "AI 销售效率工具")
    assert fp1 == fp2
    # 不同企业/分类 → 不同指纹
    assert compute_candidate_fingerprint("cmp2", "SALES_EFFICIENCY", "AI 销售效率工具") != fp1
    assert compute_candidate_fingerprint("cmp1", "COST_REDUCTION", "AI 销售效率工具") != fp1
    assert compute_candidate_fingerprint("cmp1", "SALES_EFFICIENCY", "获客服务") != fp1


def test_input_hash_stable_and_sensitive():
    h1 = compute_analysis_input_hash("cmp1", ["s1", "s2"], ["f1", "f2"], "opportunity_generator_v1")
    h2 = compute_analysis_input_hash("cmp1", ["s2", "s1"], ["f2", "f1"], "opportunity_generator_v1")
    assert h1 == h2  # 顺序无关
    h3 = compute_analysis_input_hash("cmp1", ["s1", "s3"], ["f1", "f2"], "opportunity_generator_v1")
    assert h1 != h3  # 信号变化 → hash 变化
    h4 = compute_analysis_input_hash("cmp1", ["s1", "s2"], ["f1", "f2"], "opportunity_generator_v2")
    assert h1 != h4  # prompt 版本变化 → hash 变化


def _seed_company_with_signals():
    db = SessionLocal()
    company, source, record = persist_company_with_source(db, name=f"去重测试企业{utcnow().timestamp()}")
    persist_signal(db, company, source, record, "SALES_HIRING",
                   confidence=85, evidence_text="官网招聘海外销售5名", fingerprint=f"fp_h_{company.id}", age_days=1)
    persist_signal(db, company, source, record, "OVERSEAS_EXPANSION",
                   confidence=80, evidence_text="公司宣布设立海外办事处，拓展海外市场", fingerprint=f"fp_o_{company.id}", age_days=2)
    db.commit()
    return db, company


def test_same_input_skips_reanalysis():
    db, company = _seed_company_with_signals()
    try:
        first = analyze_company_opportunities(db, company.id)
        assert first.status == "ANALYZED"
        assert first.candidates_created >= 1

        # 输入完全相同 → 跳过（关键：不每天重复分析相同内容）
        second = analyze_company_opportunities(db, company.id)
        assert second.status == "SKIPPED"
        assert second.reason == "analysis_input_unchanged"
        assert second.candidates_created == 0

        # 新 Signal 加入 → hash 变化 → 重新分析
        record = db.query(SourceRecord).filter_by(company_id=company.id).first()
        persist_signal(db, company, None, record, "FUNDING", confidence=85,
                       evidence_text="完成A轮融资5000万元", fingerprint=f"fp_f_{company.id}", age_days=1)
        db.commit()
        third = analyze_company_opportunities(db, company.id)
        assert third.status == "ANALYZED"
    finally:
        db.close()


def test_same_fingerprint_updates_not_creates():
    """同企业同 pain/solution 分类在窗口内 → 更新既有候选，不产生 10 个几乎相同的机会。"""
    db, company = _seed_company_with_signals()
    try:
        analyze_company_opportunities(db, company.id)
        candidates = db.query(OpportunityCandidate).filter_by(company_id=company.id).all()
        fingerprints = [c.fingerprint for c in candidates]
        assert len(fingerprints) == len(set(fingerprints)), "候选指纹必须唯一"

        # 再分析（force 跳过 hash 屏障）→ 同指纹候选应被更新而非新建
        before = len(candidates)
        analyze_company_opportunities(db, company.id, force=True)
        after = db.query(OpportunityCandidate).filter_by(company_id=company.id).all()
        assert len(after) == before, "同指纹候选必须更新而不是新建"
    finally:
        db.close()
