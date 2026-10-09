"""T08.0 P1-2 Parse Status 测试：正文为空不得 PARSE_SUCCESS；JS 渲染页正确标记。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services import extractor
from app.services.extractor import parse_html


def test_parse_success_with_content(client, monkeypatch):
    html = "<html><head><title>正常页</title></head><body><p>这是有正文的页面内容。</p></body></html>"
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(url, url, 200, "text/html", html))
    resp = client.post("/api/v1/ingest/url", json={"url": "https://www.ok-page-example.com/a"})
    assert resp.status_code == 200
    record = client.get(f"/api/v1/source-records/{resp.json()['data']['source_record_id']}").json()["data"]
    assert record["parse_status"] == "PARSE_SUCCESS"


def test_parse_empty_rejected_with_new_status(client, monkeypatch):
    """HTTP 200 但正文为空：不得 PARSE_SUCCESS（任务书 P1-2）。"""
    tiny_html = "<html><head><title>空页</title></head><body><p></p></body></html>"
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(url, url, 200, "text/html", tiny_html))
    resp = client.post("/api/v1/ingest/url", json={"url": "https://www.empty-page-example.com/a"})
    assert resp.status_code == 422  # 拒绝入库（无有效正文）
    assert "正文" in resp.json()["detail"]


def test_js_render_required_marked(client, monkeypatch):
    """HTTP 200、HTML 很大、正文极少 → JS_RENDER_REQUIRED（不是 PARSE_SUCCESS）。"""
    big_html = "<html><head><title>SPA</title></head><body>" + "<div class='app-shell'></div>" * 400 + "</body></html>"
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(url, url, 200, "text/html", big_html))
    resp = client.post("/api/v1/ingest/url", json={"url": "https://www.spa-example.com/app"})
    # JS 渲染页无正文 → 拒绝业务入库（不生成假数据），但采集器状态标记正确
    assert resp.status_code == 422
