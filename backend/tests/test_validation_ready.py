"""T08 Validation Ready 测试（任务书四十八：条件明确代码化）。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers_t06 import make_approved_opportunity, make_company


def _set_verification(client, company_id: str, status: str):
    with TestClient(app):
        from app.db.session import SessionLocal
        from app.models.company import Company
        with SessionLocal() as db:
            row = db.get(Company, company_id)
            row.verification_status = status
            row.organization_type = "COMPANY"
            db.commit()


def test_validation_ready_requires_all_conditions(client):
    company = make_company(client)
    # 未审核 + 未验证 → 不 ready
    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] not in ids


def test_validation_ready_with_full_chain(client):
    """完整链路：验证企业 + 已审核机会 + APPROVED 信号 + 证据>=1 + 证据分>=60。"""
    company = make_company(client)
    opp = make_approved_opportunity(client, company["id"])  # 审核 approve + 信号 APPROVED + 证据
    _set_verification(client, company["id"], "WEBSITE_VERIFIED")

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] in ids
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert row["failed_checks"] == []
    assert row["approved_opportunity_count"] >= 1
    assert row["approved_signal_count"] >= 1
    assert row["evidence_count"] >= 1
    assert data["validation_ready_count"] >= 1


def test_validation_ready_filters_by_organization_type(client):
    """默认只统计商业企业（COMPANY）；organization_type=null 查全部。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _set_verification(client, company["id"], "WEBSITE_VERIFIED")

    company_view = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in company_view["items"]]
    assert company["id"] in ids  # COMPANY 类型

    # 模拟非企业类型
    with TestClient(app):
        from app.db.session import SessionLocal
        from app.models.company import Company
        with SessionLocal() as db:
            row = db.get(Company, company["id"])
            row.organization_type = "UNIVERSITY"
            db.commit()

    company_view2 = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids2 = [x["company_id"] for x in company_view2["items"]]
    assert company["id"] not in ids2

    all_view = client.get("/api/v1/companies/validation-ready", params={"organization_type": ""}).json()["data"]
    ids3 = [x["company_id"] for x in all_view["items"]]
    assert company["id"] in ids3


def test_validation_ready_needs_evidence_score_60(client):
    """Evidence Score < 60 时不 ready（任务书四十八）。"""
    company = make_company(client)
    # 手工创建低证据分机会
    source = client.post("/api/v1/sources", json={
        "name": f"低证据源{uuid.uuid4().hex[:5]}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://lowev.example.com", "reliability_grade": "C", "reliability_score": 50,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://lowev.example.com/a", "title": "t",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘", "confidence": 60,
    }).json()["data"]
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "低证据机会", "problem": "x", "solution": "y",
        "pain_score": 70, "budget_score": 70, "intent_score": 70,
        "urgency_score": 70, "agent_fit_score": 70, "reachability_score": 50,
        "evidence_score": 40,
    }).json()["data"]
    client.post(f"/api/v1/opportunities/{opp['id']}/review", json={"action": "approve", "note": "审核"})
    _set_verification(client, company["id"], "WEBSITE_VERIFIED")

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] not in ids
