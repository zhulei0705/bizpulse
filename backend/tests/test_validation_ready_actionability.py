"""T08.1 回归：Validation Ready 必须考虑 actionability（任务书第三十节）。

已中标完毕的历史采购机会：不得仅因 Score 高进入 ACTIONABLE validation pool。
"""
import uuid

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from tests.helpers_t06 import make_company


def _make_awarded_opportunity(client: TestClient, company_id: str) -> dict:
    """构造"已中标"机会链路：CONTRACT_AWARD 信号（审计 AWARDED/HISTORICAL）+ 已审核机会。"""
    suffix = uuid.uuid4().hex[:6]
    source = client.post("/api/v1/sources", json={
        "name": f"中标源{suffix}", "source_type": "GOVERNMENT_PROCUREMENT",
        "base_url": "https://ccgp.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company_id, "url": f"https://ccgp.example.com/{suffix}",
        "title": "中标公告", "raw_text": "中标（成交）信息 供应商名称：测试公司 中标（成交）金额：100.0000000（万元）",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company_id, "source_record_id": record["id"],
        "signal_type": "CONTRACT_AWARD", "title": "中标公告", "confidence": 85,
        "payload_json": {"t08_audit": {"subject_role": "SUPPLIER", "procurement_status": "AWARDED",
                                        "actionability_status": "HISTORICAL_SIGNAL"}},
    }).json()["data"]
    pain = client.post("/api/v1/pain-points", json={
        "company_id": company_id, "category": "PROCUREMENT",
        "description": "历史采购", "confidence": 70, "status": "INFERRED",
    }).json()["data"]
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company_id, "primary_signal_id": signal["id"], "pain_point_id": pain["id"],
        "title": "历史中标机会", "problem": "p", "solution": "s",
        "pain_score": 95, "budget_score": 95, "intent_score": 95,
        "urgency_score": 95, "agent_fit_score": 95, "reachability_score": 90,
        "evidence_score": 90, "confidence": 90,
    }).json()["data"]
    client.post(f"/api/v1/opportunities/{opp['id']}/review", json={"action": "approve", "note": "审核"})
    with SessionLocal() as db:
        row = db.get(Signal, signal["id"])
        row.status = "APPROVED"
        db.commit()
    return {"signal_id": signal["id"], "opportunity_id": opp["id"]}


def _verify(client: TestClient, company_id: str):
    with TestClient(app):
        from app.models.company import Company

        with SessionLocal() as db:
            row = db.get(Company, company_id)
            row.verification_status = "WEBSITE_VERIFIED"
            row.organization_type = "COMPANY"
            db.commit()


def test_high_score_awarded_opportunity_blocked_from_validation_pool(client):
    """Score 全 95+ 的已中标机会：不得进入 validation ready（历史采购 ≠ 可行动）。"""
    company = make_company(client)
    _make_awarded_opportunity(client, company["id"])
    _verify(client, company["id"])

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] not in ids


def test_readiness_response_exposes_actionability_detail(client):
    company = make_company(client)
    _make_awarded_opportunity(client, company["id"])
    _verify(client, company["id"])

    from app.services.validation_readiness import company_readiness  # noqa

    with SessionLocal() as db:
        state = company_readiness(db, company["id"])
    assert state["checks"]["actionable_opportunity"] is False
    assert "actionable_opportunity" in state["failed_checks"]
    assert "actionable_opportunity_count" in state
    assert all(v == "HISTORICAL_SIGNAL" for v in state["opportunity_actionability"].values())


def test_live_tender_opportunity_still_eligible(client):
    """对照：未截止招标的真实机会仍可进入 validation ready。"""
    company = make_company(client)
    suffix = uuid.uuid4().hex[:6]
    source = client.post("/api/v1/sources", json={
        "name": f"招标源{suffix}", "source_type": "GOVERNMENT_PROCUREMENT",
        "base_url": "https://ccgp.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": f"https://ccgp.example.com/tender/{suffix}",
        "title": "公开招标公告",
        "raw_text": "公开招标公告 投标截止时间 2099年12月01日 09:30 项目概况：某采购项目",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "TENDER", "title": "公开招标", "confidence": 85,
    }).json()["data"]
    pain = client.post("/api/v1/pain-points", json={
        "company_id": company["id"], "category": "PROCUREMENT",
        "description": "在招采购", "confidence": 70, "status": "INFERRED",
    }).json()["data"]
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"], "pain_point_id": pain["id"],
        "title": "在招采购机会", "problem": "p", "solution": "s",
        "pain_score": 90, "budget_score": 90, "intent_score": 90,
        "urgency_score": 90, "agent_fit_score": 90, "reachability_score": 80,
        "evidence_score": 70, "confidence": 85,
    }).json()["data"]
    client.post(f"/api/v1/opportunities/{opp['id']}/review", json={"action": "approve", "note": "审核"})
    with SessionLocal() as db:
        row = db.get(Signal, signal["id"])
        row.status = "APPROVED"
        db.commit()
    _verify(client, company["id"])

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] in ids
