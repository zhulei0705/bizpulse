"""T08.0 P0-6 ContactExtractor 测试：角色区分、真实来源、Reachability 重算。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.procurement_parser import extract_procurement_contacts
from tests.helpers_t06 import make_approved_opportunity, make_company

REAL_NOTICE = """
采购人：清华大学
地址：北京市海淀区
联系方式：项目联系人张老师 010-62785000 zhang@mail.tsinghua.example.cn
代理机构名称：中招国际招标有限公司
代理机构联系方式：代理联系人李工 010-68587000 li@agency.example.cn
"""


def test_contact_roles_and_organizations():
    drafts = extract_procurement_contacts(REAL_NOTICE)
    by_type = {d.contact_type: d for d in drafts}
    assert "PURCHASER_CONTACT" in by_type
    assert "AGENCY_CONTACT" in by_type
    # 代理联系人不得归属采购单位（任务书 P0-6）
    assert by_type["AGENCY_CONTACT"].organization_name != "清华大学"


def test_campaign_stores_structured_contacts(client, monkeypatch):
    """端到端：战役采集公告 → 采购人企业 + 结构化联系人（VERIFIED_PUBLIC + source_url）。"""
    suffix = uuid.uuid4().hex[:6]
    list_page = f"""
    <html><body><a href="/cggg/zygg/zbgg/202609/t20261001_555001.htm">中标公告{suffix}</a></body></html>
    """
    notice_html = f"""
    <html><head><title>中标公告</title></head><body>
    <p>项目名称：联系提取验证项目</p>
    <p>采购人：测试采购大学{suffix}</p>
    <p>联系方式：项目联系人王老师 010-11112222 wang@test-purchaser.example.cn</p>
    <p>代理机构名称：测试代理有限公司{suffix}</p>
    <p>代理机构联系方式：代理联系人赵经理 010-33334444</p>
    <p>中标供应商名称：中标供应商科技{suffix}有限公司</p>
    <p>公告时间：2026年09月20日 09:00</p>
    </body></html>
    """
    from app.services import extractor
    from app.services.extractor import parse_html

    pages = {
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm": list_page,
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20261001_555001.htm": notice_html,
    }
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(
        url, url, 200, "text/html; charset=utf-8", pages[url]) if url in pages else (_ for _ in ()).throw(RuntimeError("404")))

    created = client.post("/api/v1/collection-campaigns", json={
        "name": f"联系人战役{suffix}", "seed_urls": ["http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm"],
        "target_company_count": 5,
    }).json()["data"]
    run = client.post(f"/api/v1/collection-campaigns/{created['id']}/run", json={"max_notices": 3})
    assert run.status_code == 200, run.text
    assert run.json()["data"].get("contacts_created", 0) >= 1

    # 采购人企业存在且联系人有角色/来源/验证状态
    companies = client.get("/api/v1/companies", params={"q": f"测试采购大学{suffix}", "page_size": 5}).json()["data"]["items"]
    assert companies, "采购人企业应已入库"
    purchaser = companies[0]
    assert purchaser["organization_type"] == "UNIVERSITY"
    contacts = client.get(f"/api/v1/companies/{purchaser['id']}/contacts").json()["data"]
    assert contacts, "采购人企业应有结构化联系人"
    types = {c["contact_type"] for c in contacts}
    assert "PURCHASER_CONTACT" in types
    for c in contacts:
        assert c["verification_status"] == "VERIFIED_PUBLIC"
        assert c["source_url"]


def test_reachability_recomputed_with_contacts(client):
    """联系人入库后重跑 T05 分析，Reachability 从 0 提升（重算验证）。"""
    suffix = uuid.uuid4().hex[:6]
    company = make_company(client)
    make_approved_opportunity(client, company["id"])

    from app.db.session import SessionLocal
    from app.models.company import CompanyContact

    with TestClient(app):
        # 先看无联系人时的 reachability（score）
        from app.analyzers.opportunity.context import load_company_context
        from app.analyzers.opportunity.reachability import compute_reachability

        with SessionLocal() as db:
            before = compute_reachability(load_company_context(db, company["id"])).score

            # 录入真实来源联系人
            db.add(CompanyContact(
                company_id=company["id"], name="王老师", phone="010-11112222",
                public_contact="010-11112222", contact_type="PURCHASER_CONTACT",
                organization_name=company["company_name"],
                source_url=f"https://ccgp.gov.cn/notice/{suffix}",
                verification_status="VERIFIED_PUBLIC", verified_public=True, confidence=80,
            ))
            db.commit()
            after = compute_reachability(load_company_context(db, company["id"])).score

    assert before <= 45  # 无联系人：仅官网底分
    # T08.2 任务书二十：分档权重 —— VERIFIED_PUBLIC 电话(55) < 官方表单(65) < 公开邮箱(80)
    assert after == 55   # 仅公开电话档（比旧版统一80分低，符合"邮箱 > 电话"分层语义）
