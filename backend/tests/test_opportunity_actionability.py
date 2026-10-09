"""T08.1 机会可行动性服务回归：AWARDED/CLOSED 机会不得进入 ACTIONABLE 验证池。"""
import uuid
from datetime import datetime,timezone

from app.db.session import SessionLocal
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.services.actionability import (
    compute_signal_actionability,
    is_actionable_for_validation,
    opportunity_actionability,
)


def _make_fixture(signal_type: str, *, raw_text: str | None = None, payload: dict | None = None) -> dict:
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:8]
        company = Company(
            company_name=f"行动性测试企业{suffix}",
            normalized_name=f"行动性测试企业{suffix}".lower(),
            organization_type="COMPANY",
            verification_status="WEBSITE_VERIFIED",
        )
        db.add(company)
        db.flush()
        source = Source(name=f"行动性测试源{suffix}", source_type="GOVERNMENT_PROCUREMENT",
                        reliability_grade="A", reliability_score=95)
        db.add(source)
        db.flush()
        record = SourceRecord(
            source_id=source.id, company_id=company.id,
            url=f"https://ccgp.example.com/{suffix}", title="公告", raw_text=raw_text,
            content_hash=f"hash-{suffix}",
        )
        db.add(record)
        db.flush()
        signal = Signal(
            company_id=company.id, source_record_id=record.id,
            signal_type=signal_type, title="测试信号",
            confidence=85, status="APPROVED", payload_json=payload or {},
            published_at=datetime.now(timezone.utc) if signal_type in {'HIRING','SALES_HIRING'} else None,
        )
        db.add(signal)
        db.flush()
        opportunity = Opportunity(
            company_id=company.id, primary_signal_id=signal.id,
            title="测试机会", problem="p", solution="s",
        )
        db.add(opportunity)
        db.commit()
        return {"company_id": company.id, "signal_id": signal.id, "opportunity_id": opportunity.id}


def test_awarded_supplier_signal_is_historical():
    fx = _make_fixture("CONTRACT_AWARD", payload={
        "t08_audit": {"subject_role": "SUPPLIER", "procurement_status": "AWARDED",
                      "actionability_status": "HISTORICAL_SIGNAL"},
    })
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        assert compute_signal_actionability(db, signal) == "HISTORICAL_SIGNAL"
        opp = db.get(Opportunity, fx["opportunity_id"])
        result = opportunity_actionability(db, opp)
        assert result["actionability_status"] == "HISTORICAL_SIGNAL"
        assert is_actionable_for_validation(result["actionability_status"]) is False


def test_awarded_buyer_signal_not_actionable():
    fx = _make_fixture("CONTRACT_AWARD", payload={
        "t08_audit": {"subject_role": "BUYER", "procurement_status": "AWARDED",
                      "actionability_status": "NOT_ACTIONABLE"},
    })
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        assert compute_signal_actionability(db, signal) == "NOT_ACTIONABLE"


def test_contract_award_without_audit_defaults_to_historical():
    """CONTRACT_AWARD 无审计信息时默认供应商侧 AWARDED（发现管线只挂供应商），不得误判为可行动。"""
    fx = _make_fixture("CONTRACT_AWARD")
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        status = compute_signal_actionability(db, signal)
        assert status == "HISTORICAL_SIGNAL"
        assert is_actionable_for_validation(status) is False


def test_open_tender_is_actionable_now():
    """招标未截止 → 可行动。"""
    raw = "某项目公开招标公告 投标截止时间 2099年12月01日 09:30 三、项目概况"
    fx = _make_fixture("TENDER", raw_text=raw)
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        status = compute_signal_actionability(db, signal)
        assert status == "ACTIONABLE_NOW"
        assert is_actionable_for_validation(status) is True


def test_closed_tender_not_actionable():
    raw = "某项目公开招标公告 投标截止时间 2020年01月01日 09:30 三、项目概况"
    fx = _make_fixture("TENDER", raw_text=raw)
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        status = compute_signal_actionability(db, signal)
        assert status == "NOT_ACTIONABLE"


def test_hiring_signal_is_actionable_now():
    """T08.2：招聘是企业当前进行中的扩张行为 → ACTIONABLE_NOW（验证门放行）。"""
    fx = _make_fixture("SALES_HIRING")
    with SessionLocal() as db:
        signal = db.get(Signal, fx["signal_id"])
        status = compute_signal_actionability(db, signal)
        assert status == "ACTIONABLE_NOW"
        assert is_actionable_for_validation(status) is True
