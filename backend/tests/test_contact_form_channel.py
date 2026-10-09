"""T08.2 WEBSITE_FORM 渠道回归（任务书十九/二十九）：与 EMAIL/PHONE 明确区分。"""
import uuid

from app.db.session import SessionLocal
from app.models.company import Company, CompanyContact
from app.services.validation_readiness import usable_contact_channels


def _mk_company_with_contact(db, *, email=None, phone=None, form=None) -> Company:
    suffix = uuid.uuid4().hex[:6]
    c = Company(company_name=f"表单渠道测试{suffix}", normalized_name=f"表单渠道测试{suffix}".lower(),
                organization_type="COMPANY", verification_status="WEBSITE_VERIFIED",
                website="https://formtest.example.com", domain="formtest.example.com")
    db.add(c)
    db.flush()
    db.add(CompanyContact(
        company_id=c.id, contact_type="GENERAL",
        email=email, phone=phone, public_contact=email or phone,
        public_profile_url=form,
        source_url=form or "https://formtest.example.com/contact",
        source_type="OFFICIAL_WEBSITE",
        verification_status="VERIFIED_PUBLIC", verified_public=True,
    ))
    db.commit()
    return c


def test_form_channel_derivable():
    """表单渠道由字段推导（public_profile_url 有值且无邮箱电话）。"""
    with SessionLocal() as db:
        c = _mk_company_with_contact(db, form="https://formtest.example.com/message")
        channels = usable_contact_channels(db, c.id)
    assert len(channels) == 1
    assert channels[0]["channel"] == "WEBSITE_FORM"
    assert channels[0]["form_url"] == "https://formtest.example.com/message"


def test_form_channel_distinct_from_email_phone():
    """WEBSITE_FORM 与 EMAIL/PHONE 是不同渠道，不得混同。"""
    with SessionLocal() as db:
        c1 = _mk_company_with_contact(db, email="a@formtest.example.com")
        c2 = _mk_company_with_contact(db, phone="010-11112222")
        c3 = _mk_company_with_contact(db, form="https://formtest.example.com/form")
        ch1 = usable_contact_channels(db, c1.id)
        ch2 = usable_contact_channels(db, c2.id)
        ch3 = usable_contact_channels(db, c3.id)
    assert ch1[0]["channel"] == "EMAIL"
    assert ch2[0]["channel"] == "PHONE"
    assert ch3[0]["channel"] == "WEBSITE_FORM"


def test_email_takes_precedence_in_channel_label():
    """同一条联系人同时有邮箱和表单时渠道归 EMAIL（主渠道优先）。"""
    with SessionLocal() as db:
        c = _mk_company_with_contact(db, email="b@formtest.example.com",
                                     form="https://formtest.example.com/form")
        channels = usable_contact_channels(db, c.id)
    assert channels[0]["channel"] == "EMAIL"
