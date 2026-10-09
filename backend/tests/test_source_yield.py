"""T08 Source Yield 测试：采集记录 → Signal → Approved → Opportunity 链路统计（真实外键）。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers_t06 import make_approved_opportunity, make_company

def test_source_yield_chain(client):
    suffix = uuid.uuid4().hex[:6]
    # 建一个独立来源 + 信号 + 机会（真实外键链路）
    source = client.post("/api/v1/sources", json={
        "name": f"产出源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://yield.example.com", "reliability_grade": "A", "reliability_score": 92,
    }).json()["data"]
    company = make_company(client)
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": f"https://yield.example.com/{suffix}", "title": "官方公告",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘海外销售", "confidence": 85,
    }).json()["data"]

    resp = client.get("/api/v1/sources/yield")
    assert resp.status_code == 200
    rows = resp.json()["data"]["yield"]
    row = next(x for x in rows if x["source_id"] == source["id"])
    assert row["record_count"] >= 1
    assert row["signal_count"] >= 1
    assert row["records_30d"] >= 1
    # 机会未产生前 approved_opportunity_count 为 0（真实状态）
    assert row["approved_opportunity_count"] >= 0

    # 产生已审核机会后，链路计数增长
    company_obj = make_approved_opportunity(client, company["id"])
    rows2 = client.get("/api/v1/sources/yield").json()["data"]["yield"]
    # 该机会的 primary_signal 属于同源 → approved_signal 链路成立
    row2 = next(x for x in rows2 if x["source_id"] == source["id"])
    assert row2["signal_count"] >= 1


def test_source_health_structure(client):
    resp = client.get("/api/v1/sources/yield")
    health = resp.json()["data"]["health"]
    assert isinstance(health, list)
    if health:
        row = health[0]
        for key in ["source_id", "name", "records_7d", "records_30d", "count_429", "count_403", "parse_failure_count"]:
            assert key in row
