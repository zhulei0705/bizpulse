"""Signal 审核测试：候选 approve/reject、正式 Signal 审核、AuditLog before/after。"""
import uuid


def _setup_candidate(client, raw="公司公告：与头部企业签署战略合作协议，共建产业生态。"):
    suffix = uuid.uuid4().hex[:5]
    company = client.post("/api/v1/companies", json={"company_name": f"审核企业{suffix}"}).json()["data"]
    src = client.post("/api/v1/sources", json={"name": f"审核源{suffix}", "source_type": "OFFICIAL_WEBSITE", "base_url": f"https://rev-{suffix}.example.com", "reliability_grade": "A", "reliability_score": 95}).json()["data"]
    record = client.post(f"/api/v1/sources/{src['id']}/records", json={"company_id": company["id"], "url": f"https://rev-{suffix}.example.com/n", "title": "公告", "raw_text": raw}).json()["data"]
    client.post(f"/api/v1/source-records/{record['id']}/analyze-signals")
    candidates = client.get("/api/v1/signal-candidates", params={"source_record_id": record["id"]}).json()["data"]["items"]
    assert candidates
    return candidates[0], record


def test_approve_candidate_creates_signal_with_audit(client):
    cand, _ = _setup_candidate(client)
    resp = client.post(f"/api/v1/signal-candidates/{cand['id']}/approve", json={"note": "证据确凿"})
    assert resp.status_code == 200
    signal_id = resp.json()["data"]["signal_id"]
    assert signal_id

    detail = client.get(f"/api/v1/signals/{signal_id}").json()["data"]
    assert detail["status"] == "APPROVED"
    assert detail["fact_summary"]
    assert detail["evidences"] and detail["evidences"][0]["quoted_text"]

    logs = client.get("/api/v1/logs/audit", params={"page_size": 30}).json()["data"]["items"]
    entry = next(l for l in logs if l["action"] == "SIGNAL_CANDIDATE_APPROVED" and l["entity_id"] == signal_id)
    assert entry["payload_json"]["before"]["status"] in {"DETECTED", "REVIEW_REQUIRED"}
    assert entry["payload_json"]["after"]["status"] == "APPROVED"
    assert entry["payload_json"]["note"] == "证据确凿"


def test_reject_candidate_blocks_signal(client):
    cand, _ = _setup_candidate(client)
    resp = client.post(f"/api/v1/signal-candidates/{cand['id']}/reject", json={"note": "证据不足"})
    assert resp.status_code == 200
    listing = client.get("/api/v1/signal-candidates", params={"status": "REJECTED"}).json()["data"]["items"]
    assert any(c["id"] == cand["id"] for c in listing)
    # 驳回后不能再次 approve
    dup = client.post(f"/api/v1/signal-candidates/{cand['id']}/approve")
    assert dup.status_code == 409


def test_already_processed_candidate_conflict(client):
    cand, _ = _setup_candidate(client)
    client.post(f"/api/v1/signal-candidates/{cand['id']}/approve")
    again = client.post(f"/api/v1/signal-candidates/{cand['id']}/approve")
    assert again.status_code == 409


def test_signal_approve_reject_with_before_after(client):
    cand, _ = _setup_candidate(client)
    signal_id = client.post(f"/api/v1/signal-candidates/{cand['id']}/approve").json()["data"]["signal_id"]

    resp = client.post(f"/api/v1/signals/{signal_id}/reject", json={"note": "复核为过期信息"})
    assert resp.status_code == 200
    detail = client.get(f"/api/v1/signals/{signal_id}").json()["data"]
    assert detail["status"] == "REJECTED"

    back = client.post(f"/api/v1/signals/{signal_id}/approve", json={"note": "恢复"})
    assert back.status_code == 200
    assert client.get(f"/api/v1/signals/{signal_id}").json()["data"]["verification_status"] == "VERIFIED"

    logs = client.get("/api/v1/logs/audit", params={"page_size": 30}).json()["data"]["items"]
    reject_log = next(l for l in logs if l["action"] == "SIGNAL_REJECTED" and l["entity_id"] == signal_id)
    assert reject_log["payload_json"]["before"]["status"] == "APPROVED"
    assert reject_log["payload_json"]["after"]["status"] == "REJECTED"
