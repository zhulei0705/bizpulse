"""人工审核测试：approve/reject/edit/ready，审核记录 + 审计日志。"""
import uuid

import pytest


@pytest.fixture()
def opportunity(client):
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={"company_name": f"审核测试企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"审核测试来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://review-test.example.com", "reliability_grade": "A", "reliability_score": 90,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://review-test.example.com/news/3", "title": "公告",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "COST_PRESSURE", "title": "原材料涨价", "confidence": 75,
    }).json()["data"]
    resp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "采购成本监控自动化", "problem": "采购成本上涨无法及时感知", "solution": "价格监控AI代理",
        "pain_score": 80, "budget_score": 70, "intent_score": 70, "urgency_score": 60,
        "agent_fit_score": 85, "reachability_score": 60, "evidence_score": 65,
    })
    assert resp.status_code == 200
    return resp.json()["data"]


def _review(client, opp_id: str, **body) -> dict:
    resp = client.post(f"/api/v1/opportunities/{opp_id}/review", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _last_review_audit(client, opp_id: str) -> dict:
    logs = client.get("/api/v1/logs/audit", params={"page_size": 50}).json()["data"]["items"]
    for item in logs:
        if item["action"] == "REVIEW" and item["entity_id"] == opp_id:
            return item
    raise AssertionError("REVIEW audit log not found")


def test_review_approve(client, opportunity):
    data = _review(client, opportunity["id"], action="approve", note="证据充分，进入验证")
    assert data["stage"] == "READY"
    assert data["review_status"] == "APPROVED"
    assert data["review_note"] == "证据充分，进入验证"
    assert data["reviewed_at"] is not None
    assert data["reviewed_by"] == "local-user"
    assert _last_review_audit(client, opportunity["id"])["payload_json"]["action"] == "approve"


def test_review_reject(client, opportunity):
    data = _review(client, opportunity["id"], action="reject", note="证据不足")
    assert data["stage"] == "REJECTED"
    assert data["review_status"] == "REJECTED"
    assert _last_review_audit(client, opportunity["id"])["payload_json"]["note"] == "证据不足"


def test_review_ready(client, opportunity):
    data = _review(client, opportunity["id"], action="ready", note="加入验证计划")
    assert data["stage"] == "READY"
    assert data["review_status"] == "APPROVED"


def test_review_edit_recomputes_score(client, opportunity):
    original_score = opportunity["total_score"]
    data = _review(client, opportunity["id"], action="edit", note="调整评分", updates={
        "title": "采购成本监控自动化（修订）",
        "evidence_score": 85,
        "reachability_score": 80,
    })
    assert data["title"] == "采购成本监控自动化（修订）"
    assert data["total_score"] != original_score
    assert data["review_status"] == "EDITED"
    # evidence=85 ≥ 60，总分提高后按真实分数定级
    expected = round(80 * 0.25 + 70 * 0.20 + 70 * 0.20 + 60 * 0.10 + 85 * 0.10 + 80 * 0.05 + 85 * 0.10, 2)
    assert data["total_score"] == expected


def test_review_edit_requires_updates(client, opportunity):
    resp = client.post(f"/api/v1/opportunities/{opportunity['id']}/review", json={"action": "edit"})
    assert resp.status_code == 422


def test_review_invalid_action(client, opportunity):
    resp = client.post(f"/api/v1/opportunities/{opportunity['id']}/review", json={"action": "destroy"})
    assert resp.status_code == 422


def test_review_missing_opportunity(client):
    resp = client.post("/api/v1/opportunities/opp_missing/review", json={"action": "approve"})
    assert resp.status_code == 404
