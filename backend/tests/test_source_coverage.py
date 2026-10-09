"""T08 Source Coverage 测试：动态聚合官网/招聘/新闻/采购/联系人覆盖。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.company_quality import source_coverage
from tests.helpers_t06 import make_approved_opportunity, make_company, make_contact


def test_coverage_all_missing_for_empty_company():
    with TestClient(app):
        from app.db.session import SessionLocal
        with SessionLocal() as db:
            suffix = uuid.uuid4().hex[:6]
            company = Company_ = None
            from app.models.company import Company
            company = Company(company_name=f"覆盖空白{suffix}", normalized_name=f"fgkb{suffix}", source_count=0)
            db.add(company)
            db.commit()
            data = source_coverage(db, company.id)
            assert data["coverage"]["WEBSITE"] is False
            assert data["coverage"]["CONTACT"] is False
            assert data["coverage_score"] == 0
            assert set(data["missing"]) == {"WEBSITE", "CAREERS", "NEWS", "PROCUREMENT", "CONTACT"}


def test_coverage_reflects_real_signals(client):
    company = make_company(client)
    make_approved_opportunity(client, company["id"])  # SALES_HIRING 信号（T04 产出）
    make_contact(client, company["id"], verified=True)

    with TestClient(app):
        from app.db.session import SessionLocal
        with SessionLocal() as db:
            data = source_coverage(db, company["id"])
            assert data["coverage"]["WEBSITE"] is True  # helper 带官网域名
            assert data["coverage"]["CAREERS"] is True  # 招聘信号
            assert data["coverage"]["NEWS"] is True  # 中标/产品类
            assert data["coverage"]["CONTACT"] is True  # 已有可用联系人
            assert data["coverage_score"] >= 4


def test_coverage_api_endpoint(client):
    company = make_company(client)
    resp = client.get(f"/api/v1/companies/coverage/{company['id']}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "coverage" in data and "missing" in data
    missing_resp = client.get("/api/v1/companies/coverage/cmp_missing")
    assert missing_resp.status_code == 404
