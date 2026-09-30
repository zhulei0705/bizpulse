"""客户机会 API 测试：后端评分、证据自动关联、筛选、阶段流转。"""
import uuid

import pytest


@pytest.fixture()
def company_signal_record(client):
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={"company_name": f"机会测试企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"机会测试来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://opp-test.example.com", "reliability_grade": "A", "reliability_score": 92,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://opp-test.example.com/news/2", "title": "官方公告2",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘海外销售经理", "confidence": 85,
    }).json()["data"]
    return company, signal, record


def _payload(company_id: str, signal_id: str | None = None, **overrides) -> dict:
    base = {
        "company_id": company_id,
        "primary_signal_id": signal_id,
        "title": "海外销售线索获取自动化",
        "problem": "海外线索获取依赖人工，效率低",
        "solution": "AI 代理自动化线索获取与初筛",
        "pain_score": 90, "budget_score": 90, "intent_score": 90,
        "urgency_score": 80, "agent_fit_score": 90, "reachability_score": 70,
        "evidence_score": 40, "confidence": 80,
    }
    base.update(overrides)
    return base


def test_create_opportunity_scores_on_backend(client, company_signal_record):
    company, signal, _ = company_signal_record
    resp = client.post("/api/v1/opportunities", json=_payload(company["id"], signal["id"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # 后端评分引擎计算：83 分；evidence=40 < 60 → 最高 B
    assert data["total_score"] == 83.0
    assert data["grade"] == "B"
    assert data["stage"] == "NEW"
    assert data["review_status"] == "PENDING"
    # 主信号自动关联为证据
    assert data["evidence_count"] == 1


def test_create_opportunity_validations(client, company_signal_record):
    company, signal, _ = company_signal_record
    assert client.post("/api/v1/opportunities", json=_payload("cmp_missing", signal["id"])).status_code == 422
    assert client.post("/api/v1/opportunities", json=_payload(company["id"], "sig_missing")).status_code == 422
    assert client.post("/api/v1/opportunities", json=_payload(company["id"], signal["id"], stage="BAD_STAGE")).status_code == 422
    # 证据强制：evidence_count=0（未关联信号）禁止生成正式机会
    no_signal = client.post("/api/v1/opportunities", json=_payload(company["id"]))
    assert no_signal.status_code == 422
    assert "待验证线索" in no_signal.json()["detail"]


def test_list_opportunities_filters(client, company_signal_record):
    company, signal, _ = company_signal_record
    created = client.post("/api/v1/opportunities", json=_payload(company["id"], signal["id"])).json()["data"]

    resp = client.get("/api/v1/opportunities", params={"company_id": company["id"]})
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["company_name"].startswith("机会测试企业")
    assert {"items", "total", "page", "page_size"} <= set(data.keys())
    assert "counts" in data

    assert client.get("/api/v1/opportunities", params={"company_id": company["id"], "min_score": 90}).json()["data"]["total"] == 0
    assert client.get("/api/v1/opportunities", params={"company_id": company["id"], "min_score": 80}).json()["data"]["total"] == 1
    assert client.get("/api/v1/opportunities", params={"company_id": company["id"], "grade": "B"}).json()["data"]["total"] == 1
    assert client.get("/api/v1/opportunities", params={"company_id": company["id"], "stage": "NEW"}).json()["data"]["total"] == 1


def test_stage_update_and_legacy_mapping(client, company_signal_record):
    company, signal, _ = company_signal_record
    opp = client.post("/api/v1/opportunities", json=_payload(company["id"], signal["id"])).json()["data"]

    resp = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "CONTACTED"})
    assert resp.json()["data"]["stage"] == "CONTACTED"

    # 旧枚举 PENDING_REVIEW 自动映射为 REVIEW
    resp = client.patch(f"/api/v1/opportunities/{opp['id']}/stage", json={"stage": "PENDING_REVIEW"})
    assert resp.json()["data"]["stage"] == "REVIEW"


def test_opportunity_detail_evidence_traceable(client, company_signal_record):
    company, signal, record = company_signal_record
    opp = client.post("/api/v1/opportunities", json=_payload(company["id"], signal["id"])).json()["data"]
    detail = client.get(f"/api/v1/opportunities/{opp['id']}")
    evidences = detail.json()["data"]["evidences"]
    assert len(evidences) == 1
    assert evidences[0]["signal_id"] == signal["id"]
    assert evidences[0]["url"] == "https://opp-test.example.com/news/2"
    assert evidences[0]["evidence_excerpt"] == "招聘海外销售经理"
