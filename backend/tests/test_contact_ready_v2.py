"""T08.2 Contact Ready v2 回归（任务书二十九）：validation_ready 且有可用渠道。"""
import uuid

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyContact
from tests.helpers_t06 import make_company, make_approved_opportunity


def _verify(client, company_id: str):
    with TestClient(app):
        with SessionLocal() as db:
            row = db.get(Company, company_id)
            row.verification_status = "WEBSITE_VERIFIED"
            row.organization_type = "COMPANY"
            db.commit()


def _add_contact(company_id: str, *, email: str | None, form: str | None = None):
    with SessionLocal() as db:
        db.add(CompanyContact(
            company_id=company_id, contact_type="GENERAL",
            email=email, phone=None, public_contact=email,
            public_profile_url=form,
            source_url=form or "https://v2.example.com/contact",
            source_type="OFFICIAL_WEBSITE",
            verification_status="VERIFIED_PUBLIC", verified_public=True,
        ))
        db.commit()


def test_contact_ready_requires_validation_ready():
    """有 VERIFIED_PUBLIC 联系人但机会链路不完整 → contact_ready=false（新定义）。"""
    company = make_company(client=None) if False else None
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        c = Company(company_name=f"仅有联系企业{suffix}", normalized_name=f"仅有联系企业{suffix}".lower(),
                    organization_type="COMPANY", verification_status="WEBSITE_VERIFIED")
        db.add(c)
        db.flush()
        db.add(CompanyContact(
            company_id=c.id, contact_type="GENERAL", email=f"a{suffix}@v2.example.com",
            public_contact=f"a{suffix}@v2.example.com",
            source_url="https://v2.example.com/contact", source_type="OFFICIAL_WEBSITE",
            verification_status="VERIFIED_PUBLIC", verified_public=True,
        ))
        db.commit()
        cid = c.id
    from app.services.validation_readiness import company_readiness

    state = company_readiness(SessionLocal(), cid)
    assert len(state["usable_contact_channels"]) == 1
    assert state["validation_ready"] is False           # 无机会链路
    assert state["contact_ready"] is False              # 新定义：必须先 validation_ready


def test_contact_ready_with_full_chain_and_email(client):
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _verify(client, company["id"])
    _add_contact(company["id"], email=f"ok{uuid.uuid4().hex[:4]}@v2.example.com")

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert row["validation_ready"] is True
    assert row["contact_ready"] is True
    assert row["usable_contact_count"] >= 1


def test_contact_ready_with_form_channel(client):
    """官方联系表单也算可用渠道（任务书十九/二十九）。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _verify(client, company["id"])
    _add_contact(company["id"], email=None, form="https://v2-form.example.com/message")

    data = client.get("/api/v1/companies/validation-ready", params={"contact_ready_only": True}).json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] in ids


def test_unverified_contact_does_not_count(client):
    """UNVERIFIED 联系人不计入可用渠道。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _verify(client, company["id"])
    suffix = uuid.uuid4().hex[:4]
    with SessionLocal() as db:
        db.add(CompanyContact(
            company_id=company["id"], contact_type="GENERAL",
            email=f"unverified{suffix}@v2.example.com",
            source_url="https://v2.example.com/x", source_type="OFFICIAL_WEBSITE",
            verification_status="UNVERIFIED", verified_public=False,
        ))
        db.commit()

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert row["validation_ready"] is True
    assert row["contact_ready"] is False  # 渠道不可用
