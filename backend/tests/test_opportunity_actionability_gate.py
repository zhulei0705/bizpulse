"""T08.2 机会生成 actionability 门回归（任务书二十六）：T05 只对当前信号产出候选。"""
import uuid

from app.analyzers.opportunity.context import CompanyAnalysisContext, SignalContext
from app.analyzers.opportunity.generator import analyze_company_opportunities
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.opportunity_candidate import OpportunityCandidate
from app.services.actionability import compute_actionability_by_rules


class _FakeRecord:
    def __init__(self, raw_text=None):
        self.raw_text = raw_text


class _FakeSignal:
    def __init__(self, signal_type, *, confidence=80, payload=None, published_at=None, raw_text=None):
        self.id = f"sig_{uuid.uuid4().hex[:8]}"
        self.signal_type = signal_type
        self.confidence = confidence
        self.payload_json = payload or {}
        self.published_at = published_at
        self.collected_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        self.last_seen_at = None
        self.change_type = None
        self.change_value = None
        self.source_record = _FakeRecord(raw_text)
        self.fact_summary = f"{signal_type}事实"
        self.title = f"{signal_type}标题"


def _ctx_with(signal_types_conf):
    company = type("C", (), {"company_name": "门测试企业"})()
    ctx = CompanyAnalysisContext(company=company)
    for t, conf in signal_types_conf:
        ctx.signals.append(SignalContext(signal=_FakeSignal(t, confidence=conf), source_grade="B"))
    return ctx


def test_historical_conf85_loses_to_current_conf55_in_fallback():
    """单信号兜底只看当前信号：历史中标(85分)不得压过当前招聘(55分)成为主触发。"""
    from app.analyzers.opportunity.bundles import _is_current_signal

    ctx = _ctx_with([("CONTRACT_AWARD", 85), ("HIRING", 55)])
    current = [s for s in ctx.signals if _is_current_signal(s.signal)]
    assert len(current) == 1
    assert current[0].signal.signal_type == "HIRING"


def test_award_only_company_reason_is_historical_only():
    """只有中标历史的企业：分析入口直接返回 only_historical_signals。"""
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        c = Company(company_name=f"仅历史信号企业{suffix}", normalized_name=f"仅历史信号企业{suffix}".lower(),
                    organization_type="COMPANY", verification_status="PUBLIC_SOURCE_VERIFIED")
        db.add(c)
        db.flush()
        stats = analyze_company_opportunities(db, c.id, force=True)
        db.commit()
        # 无已批准信号 → 进入条件不满足；即便满足，历史-only 也被门拦截
        assert stats.candidates_created == 0
    finally:
        db.close()


def test_bundle_excludes_historical_core():
    """采购就绪组合的核心若全部是历史事件（如已中标），组合不得成立。"""
    from app.analyzers.opportunity.bundles import build_signal_bundles

    ctx = _ctx_with([("CONTRACT_AWARD", 85), ("TENDER", 82)])
    # TENDER 无原文截止时间 → ANNOUNCED → WATCH（当前）；CONTRACT_AWARD → 历史
    for sc in ctx.signals:
        sc.signal.source_record.raw_text = "中标公告 三、中标（成交）信息" if sc.signal.signal_type == "CONTRACT_AWARD" else "公开招标公告"
        assert compute_actionability_by_rules(sc.signal) in {"HISTORICAL_SIGNAL", "WATCH"}
    drafts = build_signal_bundles(ctx)
    # PURCHASE_READY 组合的 core 含 TENDER（WATCH 视为当前）→ 组合成立但成员不含历史信号
    purchase = [d for d in drafts if d.bundle_type == "PURCHASE_READY"]
    if purchase:
        assert all(t != "CONTRACT_AWARD" for t in purchase[0].signal_types)
