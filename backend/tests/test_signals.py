"""商业信号 API 测试：枚举校验、人工证据URL、筛选、详情证据。"""
import uuid

import pytest


@pytest.fixture()
def company_with_record(client):
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={"company_name": f"信号测试企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"信号测试来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://signal-test.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://signal-test.example.com/news/1", "title": "官方公告",
    }).json()["data"]
    return company, record


def test_create_signal_with_source_record(client, company_with_record):
    company, record = company_with_record
    resp = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "HIRING", "title": "测试招聘信号", "confidence": 88, "reliability_score": 95,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["signal_type"] == "HIRING"
    assert data["fact_or_inference"] == "FACT"


def test_create_signal_with_evidence_url_creates_source_record(client, company_with_record):
    company, _ = company_with_record
    resp = client.post("/api/v1/signals", json={
        "company_id": company["id"], "signal_type": "FUNDING", "title": "测试融资信号",
        "description": "宣布完成B轮融资", "evidence_url": "https://news.example.com/funding/9", "confidence": 70,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["evidence"]["url"] == "https://news.example.com/funding/9"
    assert data["evidence"]["source_name"] == "人工录入证据"

    record_resp = client.get(f"/api/v1/source-records/{data['source_record_id']}")
    assert record_resp.status_code == 200
    assert record_resp.json()["data"]["url"] == "https://news.example.com/funding/9"


def test_signal_type_enum_enforced(client, company_with_record):
    company, record = company_with_record
    resp = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "NOT_A_TYPE", "title": "非法类型",
    })
    assert resp.status_code == 422


def test_signal_requires_traceable_evidence(client, company_with_record):
    company, _ = company_with_record
    resp = client.post("/api/v1/signals", json={
        "company_id": company["id"], "signal_type": "HIRING", "title": "无证据信号",
    })
    assert resp.status_code == 422


def test_signal_invalid_company_rejected(client, company_with_record):
    _, record = company_with_record
    resp = client.post("/api/v1/signals", json={
        "company_id": "cmp_missing", "source_record_id": record["id"], "signal_type": "HIRING", "title": "x",
    })
    assert resp.status_code == 422


def test_list_signals_filters(client, company_with_record):
    company, record = company_with_record
    client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "HIRING", "title": "高置信信号", "confidence": 90,
    })
    client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "FUNDING", "title": "低置信信号", "confidence": 30,
    })

    resp = client.get("/api/v1/signals", params={"signal_type": "HIRING"})
    assert all(item["signal_type"] == "HIRING" for item in resp.json()["data"]["items"])

    resp = client.get("/api/v1/signals", params={"min_confidence": 60})
    assert all(item["confidence"] >= 60 for item in resp.json()["data"]["items"])

    resp = client.get("/api/v1/signals", params={"company_id": company["id"]})
    assert resp.json()["data"]["total"] == 2

    resp = client.get("/api/v1/signals", params={"fact_or_inference": "FACT"})
    assert all(item["fact_or_inference"] == "FACT" for item in resp.json()["data"]["items"])


def test_signal_detail_contains_evidence(client, company_with_record):
    company, record = company_with_record
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "EXPANSION", "title": "扩张信号",
    }).json()["data"]
    detail = client.get(f"/api/v1/signals/{signal['id']}")
    assert detail.status_code == 200
    evidence = detail.json()["data"]["evidence"]
    assert evidence["url"] == "https://signal-test.example.com/news/1"
    assert evidence["reliability_grade"] == "A"
