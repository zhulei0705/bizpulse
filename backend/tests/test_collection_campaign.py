"""T08 采集战役测试：CRUD、真实性 Gate（seed_urls 必填）、run 管线（Mock HTTP）。"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _campaign(client, **overrides):
    suffix = uuid.uuid4().hex[:6]
    body = {
        "name": f"企业池扩充战役{suffix}",
        "market": "采购场景",
        "keywords": ["仪器", "检测"],
        "source_types": ["PROCUREMENT"],
        "seed_urls": ["http://www.ccgp.gov.cn/cggg/zbgg/index.htm"],
        "target_company_count": 30,
    }
    body.update(overrides)
    return client.post("/api/v1/collection-campaigns", json=body)


def test_campaign_requires_seed_urls(client):
    resp = client.post("/api/v1/collection-campaigns", json={"name": "无来源战役", "seed_urls": []})
    assert resp.status_code == 422
    assert "seed_urls" in resp.json()["detail"]


def test_campaign_crud_and_progress(client):
    created = _campaign(client).json()["data"]
    assert created["status"] == "DRAFT"
    assert created["target_company_count"] == 30

    lst = client.get("/api/v1/collection-campaigns").json()["data"]
    assert lst["total"] >= 1

    detail = client.get(f"/api/v1/collection-campaigns/{created['id']}").json()["data"]
    assert detail["market"] == "采购场景"

    progress = client.get(f"/api/v1/collection-campaigns/{created['id']}/progress").json()["data"]
    assert progress["status"] == "DRAFT"
    assert progress["progress"] == {}


def test_campaign_run_pipeline_with_mock_fetch(client, monkeypatch):
    """run 管线（Mock HTTP）：列表页 → 公告 → 提取供应商 → Company 入库 + CONTRACT_AWARD 信号。"""
    suffix = uuid.uuid4().hex[:6]
    company_a = f"华谱科仪{suffix}有限公司"
    company_b = f"恒泰检测{suffix}股份有限公司"

    list_page = """
    <html><body>
      <a href="/cggg/zbgg/202609/t20261001_111001.htm">结果公告一</a>
      <a href="/cggg/zbgg/202609/t20261001_111002.htm">结果公告二</a>
      <a href="https://other-site.com/x">外链</a>
    </body></html>
    """
    notice_template = """
    <html><head><title>{title}</title></head><body>
    <p>项目编号：GC-{n}</p><p>项目名称：实验室仪器采购项目</p>
    <p>中标供应商名称：{supplier}</p><p>中标金额：￥{amount}</p>
    <p>采购人：某研究所</p>
    </body></html>
    """
    from app.services import extractor
    from app.services.extractor import parse_html

    pages = {
        "http://www.ccgp.gov.cn/cggg/zbgg/index.htm": list_page,
        "http://www.ccgp.gov.cn/cggg/zbgg/202609/t20261001_111001.htm": notice_template.format(title="结果公告一", n="01", supplier=company_a, amount="1,280,000"),
        "http://www.ccgp.gov.cn/cggg/zbgg/202609/t20261001_111002.htm": notice_template.format(title="结果公告二", n="02", supplier=company_b, amount="880,000"),
    }

    def _fake_fetch(url):
        if url in pages:
            return parse_html(url, url, 200, "text/html; charset=utf-8", pages[url])
        raise RuntimeError("404 not found")

    monkeypatch.setattr(extractor, "fetch_public_page", _fake_fetch)

    created = _campaign(client, seed_urls=["http://www.ccgp.gov.cn/cggg/zbgg/index.htm"], target_company_count=30).json()["data"]
    resp = client.post(f"/api/v1/collection-campaigns/{created['id']}/run", json={"max_notices": 5})
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["notices_fetched"] == 2
    # P0-6：采购人（某研究所）也作为业务主体入库 → 2 供应商 + 1 采购人 = 3
    assert result["companies_created"] == 3
    assert result["signals_created"] == 2

    # 企业入正式库且带 T08 字段
    companies = client.get("/api/v1/companies", params={"page_size": 100}).json()["data"]["items"]
    names = {c["company_name"] for c in companies}
    assert company_a in names and company_b in names
    row_a = next(c for c in companies if c["company_name"] == company_a)
    assert row_a["organization_type"] == "COMPANY"
    assert row_a["verification_status"] == "PUBLIC_SOURCE_VERIFIED"
    assert row_a["discovery_source_url"]

    # CONTRACT_AWARD 信号待人工批准（VALID，不自动 APPROVED）
    signals = client.get("/api/v1/signals", params={"company_id": row_a["id"]}).json()["data"]["items"]
    assert any(s["signal_type"] == "CONTRACT_AWARD" and s["status"] == "REVIEW" for s in signals)

    progress = client.get(f"/api/v1/collection-campaigns/{created['id']}/progress").json()["data"]
    assert progress["progress"]["finished"] is True


def test_campaign_run_single_notice_failure_does_not_break_batch(client, monkeypatch):
    """单条公告失败不回滚整批（任务书三十一）。"""
    suffix = uuid.uuid4().hex[:6]
    list_page = """
    <html><body>
      <a href="/cggg/zbgg/202609/t20261001_222001.htm">会失败的公告</a>
      <a href="/cggg/zbgg/202609/t20261001_222002.htm">会成功的公告</a>
    </body></html>
    """
    ok_notice = f"""
    <html><head><title>成功公告</title></head><body>
    <p>中标供应商名称：稳态科技{suffix}有限公司</p>
    </body></html>
    """
    from app.services import extractor
    from app.services.extractor import parse_html

    pages = {
        "http://www.ccgp.gov.cn/cggg/zbgg/index.htm": list_page,
        "http://www.ccgp.gov.cn/cggg/zbgg/202609/t20261001_222002.htm": ok_notice,
    }

    def _fake_fetch(url):
        if url in pages:
            return parse_html(url, url, 200, "text/html; charset=utf-8", pages[url])
        raise RuntimeError("connection refused")  # 第一条失败

    monkeypatch.setattr(extractor, "fetch_public_page", _fake_fetch)

    created = _campaign(client, seed_urls=["http://www.ccgp.gov.cn/cggg/zbgg/index.htm"]).json()["data"]
    resp = client.post(f"/api/v1/collection-campaigns/{created['id']}/run", json={"max_notices": 5})
    assert resp.status_code == 200
    result = resp.json()["data"]
    assert result["companies_created"] == 1
    assert any("notice_fetch_failed" in e for e in result["errors"])
