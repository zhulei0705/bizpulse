"""T08 Contact Ready 测试（任务书四十九~五十一：与 Validation Ready 分开统计）。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.company import Company
from tests.helpers_t06 import make_approved_opportunity, make_company, make_contact


def _set_org(client, company_id: str, org_type: str = "COMPANY"):
    with TestClient(app):
        with SessionLocal() as db:
            row = db.get(Company, company_id)
            row.organization_type = org_type
            row.verification_status = "WEBSITE_VERIFIED"
            db.commit()


def test_contact_ready_separate_from_validation_ready(client):
    """validation_ready=true 但 contact_ready=false：机会不错但暂时找不到联系人（真实状态）。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _set_org(client, company["id"])
    # 不创建联系人

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next((x for x in data["items"] if x["company_id"] == company["id"]), None)
    assert row is not None, "应通过 Validation Ready"
    assert row["validation_ready"] is True
    assert row["contact_ready"] is False
    assert row["usable_contact_count"] == 0


def test_contact_ready_with_verified_contact(client):
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _set_org(client, company["id"])
    make_contact(client, company["id"], verified=True)  # 真实来源联系人

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert row["contact_ready"] is True
    assert row["usable_contact_count"] >= 1
    assert data["contact_ready_count"] >= 1


def test_contact_ready_requires_real_source_contact(client):
    """UNVERIFIED 联系人不计入 Contact Ready（必须 VERIFIED_PUBLIC/USER_PROVIDED）。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _set_org(client, company["id"])
    make_contact(client, company["id"], verified=False)  # 未核实

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next((x for x in data["items"] if x["company_id"] == company["id"]), None)
    assert row is not None
    assert row["contact_ready"] is False
