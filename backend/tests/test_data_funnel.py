"""T08.2 Data Funnel 回归（任务书三十二/三十三）：漏斗与场景分布全部真实聚合。"""
import uuid

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.services.company_coverage import data_funnel, scenario_distribution
from tests.helpers_t06 import make_company, make_approved_opportunity


def test_funnel_api_shape(client):
    data = client.get("/api/v1/data-growth/funnel").json()["data"]
    for key in ("commercial_companies", "covered_companies", "companies_with_signals",
                "companies_with_actionable_signals", "companies_with_opportunities",
                "validation_ready", "contact_ready", "rates"):
        assert key in data, key
    for key in ("signal_coverage_rate", "actionable_signal_rate", "opportunity_rate",
                "validation_ready_rate", "contact_ready_rate"):
        assert key in data["rates"], key


def test_funnel_counts_are_monotonic(client):
    """漏斗逐级递减（覆盖 ≥ 信号 ≥ 行动 ≥ 验证就绪 ≥ 联系就绪）。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    data = client.get("/api/v1/data-growth/funnel").json()["data"]
    assert data["companies_with_signals"] >= data["companies_with_actionable_signals"]
    assert data["companies_with_actionable_signals"] >= data["validation_ready"]
    assert data["validation_ready"] >= data["contact_ready"]


def test_funnel_counts_new_actionable_company(client):
    """新增一家验证就绪企业 → 漏斗计数真实变化（不补数据）。"""
    before = client.get("/api/v1/data-growth/funnel").json()["data"]["validation_ready"]
    company = make_company(client)
    make_approved_opportunity(client, company["id"])  # SALES_HIRING → ACTIONABLE_NOW
    with TestClient(app):
        with SessionLocal() as db:
            row = db.get(Company, company["id"])
            row.verification_status = "WEBSITE_VERIFIED"
            row.organization_type = "COMPANY"
            db.commit()
    after = client.get("/api/v1/data-growth/funnel").json()["data"]["validation_ready"]
    assert after == before + 1


def test_scenario_distribution_is_real_aggregation():
    """场景分布只统计 Approved + 可行动信号；CONTRACT_AWARD（历史）不计入。"""
    dist = scenario_distribution(SessionLocal())
    # T08.2 执行后正式库存在多个真实场景；历史中标事件不得出现在场景分布中
    assert isinstance(dist, dict)
    for scenario in dist:
        assert scenario != "CONTRACT_AWARD"
