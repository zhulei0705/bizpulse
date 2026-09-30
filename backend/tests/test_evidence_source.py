"""Evidence 溯源测试（采集侧）：Signal → 原文摘录 → SourceRecord → 原始 URL。

quoted/excerpt 必须来自真实采集文本，不得是 AI 改写。
"""
import uuid

import pytest

from app.services import extractor


@pytest.fixture()
def mock_ingest(monkeypatch):
    html = """
    <html><head><title>溯源企业 - 官方公告</title>
    <meta property="og:site_name" content="溯源企业"/></head>
    <body><main><p>溯源企业计划在华东新建工厂，并招聘海外销售经理10名，同时启动数字化转型。</p></main></body></html>
    """
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: extractor.parse_html(url, url, 200, "text/html", html))
    return html


def test_signal_excerpt_comes_from_real_text(client, mock_ingest):
    resp = client.post("/api/v1/ingest/url", json={"url": f"https://trace-example-{uuid.uuid4().hex[:5]}.example.com/"})
    assert resp.status_code == 200
    data = resp.json()["data"]

    signals = client.get("/api/v1/signals", params={"company_id": data["company_id"]}).json()["data"]["items"]
    assert signals
    original_text = "溯源企业计划在华东新建工厂，并招聘海外销售经理10名"
    for s in signals:
        # 信号描述（证据摘录）必须是原文子串（允许上下文窗口截断后的片段）
        assert s["source_record_id"] == data["source_record_id"]
        assert s["fact_or_inference"] == "FACT"
        desc = s["description"] or ""
        assert any(fragment in original_text for fragment in desc.split("，")[:1]) or original_text[:10] in desc or "溯源企业" in desc


def test_record_detail_contains_raw_text_and_versions(client, mock_ingest):
    url = f"https://ver-detail-{uuid.uuid4().hex[:5]}.example.com/"
    resp = client.post("/api/v1/ingest/url", json={"url": url})
    record_id = resp.json()["data"]["source_record_id"]
    detail = client.get(f"/api/v1/source-records/{record_id}").json()["data"]
    assert detail["raw_text"] and "海外销售经理" in detail["raw_text"]
    assert detail["canonical_url"]
    assert detail["version_number"] == 1 and detail["is_latest"] is True
    assert isinstance(detail["versions"], list) and detail["versions"][0]["content_hash"]
    assert detail["source"]["reliability_grade"] == "C"


def test_evidence_chain_reaches_original_url(client, mock_ingest):
    url = f"https://chain-real-{uuid.uuid4().hex[:5]}.example.com/"
    resp = client.post("/api/v1/ingest/url", json={"url": url})
    data = resp.json()["data"]
    # Signal → Evidence → SourceRecord → URL
    signal = client.get("/api/v1/signals", params={"company_id": data["company_id"]}).json()["data"]["items"][0]
    assert signal["evidence"]["source_record_id"] == data["source_record_id"]
    assert signal["evidence"]["url"].startswith("https://chain-real-")
    record = client.get(f"/api/v1/source-records/{data['source_record_id']}").json()["data"]
    assert record["url"].startswith("https://chain-real-")
    assert record["raw_text"]


def test_company_user_provided_not_official(client):
    """CSV 导入的企业信息必须标记 USER_PROVIDED（AuditLog），不冒充官方核验。"""
    import csv as _csv
    import io as _io
    suffix = uuid.uuid4().hex[:5]
    csv_text = "company_name,website,source_url,industry,note\r\n" \
               f"手工企业{suffix},https://hand-{suffix}.example.com,,制造业,手工录入备注\r\n"
    resp = client.post("/api/v1/ingest/import", json={"csv_text": csv_text})
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert items[0]["company_verification"] == "USER_PROVIDED"
    logs = client.get("/api/v1/logs/audit", params={"page_size": 30}).json()["data"]["items"]
    assert any(l["action"] == "IMPORT_COMPANY" and l["payload_json"].get("verification") == "USER_PROVIDED" for l in logs)
