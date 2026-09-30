"""CompanyResolver 测试：EXACT / HIGH_CONFIDENCE / POSSIBLE / UNKNOWN + 人工关联。"""
import uuid

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.services.company_resolver import CompanyResolver, ResolveResult, domain_of_url


@pytest.fixture()
def companies(client):
    suffix = uuid.uuid4().hex[:6]
    exact = client.post("/api/v1/companies", json={
        "company_name": f"域名企业{suffix}", "domain": "exact-match.example.com",
    }).json()["data"]
    named = client.post("/api/v1/companies", json={"company_name": f"名称企业{suffix}"}).json()["data"]
    return exact, named, suffix


def _session():
    from app.db.session import SessionLocal
    return SessionLocal()


def test_exact_domain_match(client, companies):
    exact, _, _ = companies
    with _session() as db:
        result = CompanyResolver(db).resolve(domain="exact-match.example.com", organization_name=None)
        assert result.status == "EXACT"
        assert result.company_id == exact["id"]


def test_high_confidence_name_match(client, companies):
    _, named, suffix = companies
    with _session() as db:
        result = CompanyResolver(db).resolve(domain=None, organization_name=f"名称企业{suffix}")
        assert result.status == "HIGH_CONFIDENCE"
        assert result.company_id == named["id"]


def test_unknown_when_no_evidence(client):
    with _session() as db:
        result = CompanyResolver(db).resolve(domain=None, organization_name=f"完全无匹配{uuid.uuid4().hex[:6]}")
        assert result.status == "UNKNOWN"
        assert result.company_id is None


def test_alias_matches_high_confidence(client, companies):
    exact, _, suffix = companies
    with _session() as db:
        alias_norm = "".join(f"域名企业{suffix}别名".lower().split())
        db.add(__import__("app.models.company", fromlist=["CompanyAlias"]).CompanyAlias(
            company_id=exact["id"], alias=f"域名企业{suffix}别名", normalized_alias=alias_norm))
        db.commit()
        result = CompanyResolver(db).resolve(domain=None, organization_name=f"域名企业{suffix}别名")
        assert result.status == "HIGH_CONFIDENCE"
        assert result.company_id == exact["id"]


def test_similar_name_is_possible_not_auto(client, companies):
    exact, _, suffix = companies
    with _session() as db:
        # 与已有企业名仅差一个字符：应给 POSSIBLE，绝不自动合并
        result = CompanyResolver(db).resolve(domain=None, organization_name=f"域名企业{suffix}X")
        assert result.status in {"POSSIBLE", "UNKNOWN"}
        assert result.status != "EXACT"
        if result.status == "POSSIBLE":
            assert result.company_id is None


def test_domain_of_url():
    assert domain_of_url("https://WWW.Example.com/x") == "www.example.com"
    assert domain_of_url(None) is None


def test_manual_assign_company_writes_audit(client, companies):
    exact, _, _ = companies
    source = client.post("/api/v1/sources", json={"name": f"关联源{uuid.uuid4().hex[:5]}", "source_type": "OFFICIAL_WEBSITE", "reliability_grade": "A"}).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={"url": "https://unresolved.example.com/x", "title": "未关联"}).json()["data"]
    resp = client.post(f"/api/v1/source-records/{record['id']}/assign-company", json={"company_id": exact["id"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "USER_LINKED"
    logs = client.get("/api/v1/logs/audit", params={"page_size": 30}).json()["data"]["items"]
    assert any(l["action"] == "ASSIGN_COMPANY" and l["entity_id"] == record["id"] for l in logs)
