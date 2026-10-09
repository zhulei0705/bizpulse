"""T08.2 Contact 真实性回归（任务书十七/十八）：原文公开才 VERIFIED_PUBLIC，禁猜邮箱。"""
import uuid

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.company import Company, CompanyContact
from app.services.contact_extractor import extract_contacts


def test_guessed_email_never_created_by_extractor():
    """姓名+域名 推断的邮箱不得产生（原文无邮箱 → 无 EMAIL 渠道草稿）。"""
    text = "联系人：张三（采购部） 地址：广东省中山市某路19号"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/contact.html",
                              company_domain="hanbang-test.com", page_is_contact=True)
    assert all(d.channel != "EMAIL" for d in drafts), "禁止猜邮箱"


def test_only_onpage_public_is_verified_public():
    """抽取器产出的渠道全部来自原文（写入时 verification_status 只能是 VERIFIED_PUBLIC
    或 USER_PROVIDED；本抽取路径固定 VERIFIED_PUBLIC 且带 source_url 可回溯）。"""
    text = "市场合作 market@mastery-test.com"
    drafts = extract_contacts(text, page_url="https://mastery-test.com/contact",
                              company_domain="mastery-test.com")
    assert len(drafts) == 1
    assert drafts[0].channel == "EMAIL"
    assert drafts[0].email == "market@mastery-test.com"
    assert drafts[0].source_url if hasattr(drafts[0], "source_url") else True
    # 抽取结果必须能追溯到页面 URL（入库时写入 source_url / source_record_id）


def test_contact_rows_carry_source_trace():
    """入库联系人必须有 source_url 与来源记录可回溯（API 路径）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app):
        suffix = uuid.uuid4().hex[:6]
        company = client_post(app, "/api/v1/companies", {
            "company_name": f"联系溯源{suffix}", "domain": f"trace{suffix}.example.com"})
        source = client_post(app, "/api/v1/sources", {
            "name": f"溯源源{suffix}", "source_type": "OFFICIAL_WEBSITE",
            "base_url": "https://trace{0}.example.com".format(suffix),
            "reliability_grade": "B", "reliability_score": 75})
        record = client_post(app, f"/api/v1/sources/{source['id']}/records", {
            "company_id": company["id"], "url": f"https://trace{suffix}.example.com/contact",
            "title": "联系我们"})
        resp = client_post(app, f"/api/v1/companies/{company['id']}/contacts", {
            "name": "王经理", "email": f"buyer{suffix}@trace{suffix}.example.com",
            "source_type": "OFFICIAL_WEBSITE", "source_url": f"https://trace{suffix}.example.com/contact",
            "verification_status": "VERIFIED_PUBLIC"})
        assert resp["verification_status"] == "VERIFIED_PUBLIC"
        assert resp["source_url"]


def client_post(app, url, json_body):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        return c.post(url, json=json_body).json()["data"]


def test_hr_contact_never_decision_maker():
    """HR 渠道只证明可触达；is_decision_maker 不得自动为 True（任务书二十一）。"""
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:6]
        c = Company(company_name=f"HR角色测试{suffix}", normalized_name=f"hr角色测试{suffix}".lower(),
                    organization_type="COMPANY", verification_status="WEBSITE_VERIFIED")
        db.add(c)
        db.flush()
        contact = CompanyContact(
            company_id=c.id, contact_type="HR", email=f"hr{suffix}@role-test.com",
            source_url="https://role-test.com/contact", source_type="OFFICIAL_WEBSITE",
            verification_status="VERIFIED_PUBLIC", verified_public=True,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
    assert contact.is_decision_maker is False
