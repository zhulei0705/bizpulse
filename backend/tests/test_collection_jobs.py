"""CollectionJob 测试：sources/{id}/run、状态机、明细统计、逐 URL 日志。"""
import uuid

import pytest

from app.services import extractor


@pytest.fixture()
def runnable_source(client):
    suffix = uuid.uuid4().hex[:6]
    return client.post("/api/v1/sources", json={
        "name": f"执行源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": f"https://run-test-{suffix}.example.com/", "reliability_grade": "A", "reliability_score": 95,
        "collector_type": "web_page", "collection_frequency": "daily", "config_json": {},
    }).json()["data"]


def _mock_page(monkeypatch, html="<html><head><title>执行页</title></head><body><p>本页招聘工程师。</p></body></html>"):
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: extractor.parse_html(url, url, 200, "text/html", html))


def test_run_source_success(client, runnable_source, monkeypatch):
    _mock_page(monkeypatch)
    resp = client.post(f"/api/v1/sources/{runnable_source['id']}/run")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "SUCCESS"
    assert data["items_found"] == 1
    assert data["items_created"] == 1
    assert data["items_updated"] == 0


def test_run_source_second_time_skips(client, runnable_source, monkeypatch):
    _mock_page(monkeypatch)
    client.post(f"/api/v1/sources/{runnable_source['id']}/run")
    second = client.post(f"/api/v1/sources/{runnable_source['id']}/run").json()["data"]
    assert second["items_found"] == 1
    assert second["items_skipped"] == 1
    assert second["items_created"] == 0
    assert second["status"] == "SUCCESS"


def test_run_source_updates_last_success(client, runnable_source, monkeypatch):
    _mock_page(monkeypatch)
    client.post(f"/api/v1/sources/{runnable_source['id']}/run")
    detail = client.get(f"/api/v1/sources/{runnable_source['id']}").json()["data"]
    assert detail["last_run_at"] is not None
    assert detail["last_success_at"] is not None


def test_job_detail_contains_run_log(client, runnable_source, monkeypatch):
    _mock_page(monkeypatch)
    run = client.post(f"/api/v1/sources/{runnable_source['id']}/run").json()["data"]
    detail = client.get(f"/api/v1/jobs/{run['job_id']}").json()["data"]
    assert detail["job_type"] == "MANUAL"
    assert detail["items_found"] == 1
    assert detail["run_log"] and detail["run_log"][0]["url"].startswith("https://run-test-")
    assert detail["run_log"][0]["status"] == "HTTP_200"
    assert detail["run_log"][0]["latency_ms"] >= 0


def test_run_disabled_source_rejected(client, runnable_source):
    client.patch(f"/api/v1/sources/{runnable_source['id']}", json={"enabled": False})
    resp = client.post(f"/api/v1/sources/{runnable_source['id']}/run")
    assert resp.status_code == 422


def test_invalid_collector_rejected(client):
    suffix = uuid.uuid4().hex[:5]
    source = client.post("/api/v1/sources", json={
        "name": f"坏配置源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": None, "collector_type": "web_page",
    }).json()["data"]
    resp = client.post(f"/api/v1/sources/{source['id']}/run")
    assert resp.status_code == 422
