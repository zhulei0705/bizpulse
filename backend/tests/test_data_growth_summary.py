"""T08 Data Growth summary/gap 测试：真实统计与缺口上报。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers_t06 import make_approved_opportunity, make_company, make_contact


def test_summary_reflects_real_data(client):
    data = client.get("/api/v1/data-growth/summary").json()["data"]
    for key in ["company_count", "verified_company_count", "company_type_distribution", "source_count",
                "source_records", "approved_signals", "review_signals", "approved_opportunities",
                "review_opportunities", "validation_ready_companies", "contact_ready_companies"]:
        assert key in data
    assert data["company_count"] >= 1


def test_summary_type_distribution(client):
    suffix = uuid.uuid4().hex[:6]
    company = make_company(client)
    from fastapi.testclient import TestClient
    with TestClient(app):
        from app.db.session import SessionLocal
        from app.models.company import Company
        with SessionLocal() as db:
            row = db.get(Company, company["id"])
            row.organization_type = "COMPANY"
            db.commit()

    data = client.get("/api/v1/data-growth/summary").json()["data"]
    assert data["company_type_distribution"].get("COMPANY", 0) >= 1


def test_gap_reports_shortfall_honestly(client):
    data = client.get("/api/v1/data-growth/gap").json()["data"]
    gaps = {g["target"]: g for g in data["gaps"]}
    assert gaps["companies"]["target_count"] == 100
    assert gaps["approved_signals"]["target_count"] == 50
    assert gaps["approved_opportunities"]["target_count"] == 20
    assert gaps["validation_ready"]["target_count"] == 30
    for g in gaps.values():
        assert g["shortfall"] == max(0, g["target_count"] - g["current"])
    # 正式库/测试库当前都达不到全部目标（如未达成，如实反映）
    if not data["all_targets_met"]:
        assert "继续" in data["message"] or "未达成" in data["message"]


def test_quality_gate_stats(client):
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    make_contact(client, company["id"], verified=True)
    data = client.get("/api/v1/data-growth/quality").json()["data"]
    for key in ["company_count", "duplicate_count", "duplicate_rate_pct", "website_coverage_pct",
                "recent_signal_coverage_pct", "avg_company_data_quality", "collection_failure_rate_pct", "stage_gate"]:
        assert key in data
    assert data["stage_gate"]["current_stage_target"] in [30, 100, 300]
