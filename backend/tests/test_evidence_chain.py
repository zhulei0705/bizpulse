"""证据链完整性测试（真实数据强制规范）：

- Opportunity 必须至少关联 1 Signal + 1 Evidence（evidence_count=0 禁止生成正式机会）
- D 级来源不得形成高等级商业机会（证据分钳制）
- 人工审核通过后证据验证状态联动（verification_status / last_verified_at）
- 审计日志记录修改前/修改后
- URL 采集证据快照（source_reliability）与空正文拒绝

HTTP 抓取全部 Mock，不访问公网。
"""
import uuid

import pytest

from app.services import extractor
from app.services.extractor import FetchedPage

EMPTY_HTML = "<html><head><title></title></head><body>   </body></html>"


@pytest.fixture()
def mock_fetch(monkeypatch):
    def _fake_fetch(url: str) -> FetchedPage:
        html = """
        <html><head><title>链路测试企业 - 官网</title>
        <meta property="og:site_name" content="链路测试企业"/></head>
        <body><main><p>链路测试企业正在招聘海外销售经理，并宣布完成A轮融资。</p></main></body></html>
        """
        return extractor.parse_html(url, url, 200, "text/html; charset=utf-8", html)

    monkeypatch.setattr(extractor, "fetch_public_page", _fake_fetch)
    return _fake_fetch


def _setup_company_signal(client, source_grade: str = "A", suffix: str | None = None):
    suffix = suffix or uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={"company_name": f"证据链企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"证据链来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://chain-test.example.com", "reliability_grade": source_grade,
        "reliability_score": 95 if source_grade == "A" else 30,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://chain-test.example.com/news/1", "title": "官方公告",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘海外销售经理", "confidence": 85,
    }).json()["data"]
    return company, signal, record, source


def test_opportunity_requires_signal_evidence(client):
    company, signal, record, _ = _setup_company_signal(client)
    payload = {
        "company_id": company["id"], "title": "无证据机会", "problem": "p", "solution": "s",
        "pain_score": 80, "budget_score": 80, "intent_score": 80, "urgency_score": 80,
        "agent_fit_score": 80, "reachability_score": 80, "evidence_score": 80,
    }
    # evidence_count=0：禁止生成正式 Opportunity
    resp = client.post("/api/v1/opportunities", json=payload)
    assert resp.status_code == 422
    assert "待验证线索" in resp.json()["detail"]

    # 关联信号后创建成功，且自动挂接证据
    resp = client.post("/api/v1/opportunities", json={**payload, "primary_signal_id": signal["id"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["evidence_count"] == 1

    detail = client.get(f"/api/v1/opportunities/{data['id']}").json()["data"]
    assert detail["evidences"][0]["signal_id"] == signal["id"]
    assert detail["evidences"][0]["url"] == "https://chain-test.example.com/news/1"


def test_grade_d_source_cannot_form_high_grade_opportunity(client):
    company, signal, _, _ = _setup_company_signal(client, source_grade="D")
    resp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "D级来源高分包机", "problem": "p", "solution": "s",
        "pain_score": 100, "budget_score": 100, "intent_score": 100, "urgency_score": 100,
        "agent_fit_score": 100, "reachability_score": 100, "evidence_score": 100,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    # D 级来源 → evidence_score 钳制到 ≤59 → 证据门槛生效，等级最高 B
    assert data["evidence_score"] <= 59
    assert data["grade"] in {"B", "C", "D"}
    assert data["grade"] not in {"A", "S"}


def test_approve_verifies_evidence_chain(client):
    company, signal, record, _ = _setup_company_signal(client)
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "验证状态联动机会", "problem": "p", "solution": "s",
        "pain_score": 70, "budget_score": 70, "intent_score": 70, "urgency_score": 60,
        "agent_fit_score": 75, "reachability_score": 60, "evidence_score": 70,
    }).json()["data"]

    # 创建后证据均为未验证
    rec_before = client.get(f"/api/v1/source-records/{record['id']}").json()["data"]
    assert rec_before["verification_status"] == "UNVERIFIED"
    assert rec_before["source_reliability"] == "A"

    review = client.post(f"/api/v1/opportunities/{opp['id']}/review", json={"action": "approve", "note": "证据核实通过"})
    assert review.status_code == 200

    rec_after = client.get(f"/api/v1/source-records/{record['id']}").json()["data"]
    assert rec_after["verification_status"] == "VERIFIED"
    assert rec_after["last_verified_at"] is not None

    sig_after = client.get(f"/api/v1/signals/{signal['id']}").json()["data"]
    assert sig_after["verification_status"] == "VERIFIED"


def test_review_audit_records_before_and_after(client):
    company, signal, _, _ = _setup_company_signal(client)
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "审计前后对照机会", "problem": "p", "solution": "s",
        "pain_score": 60, "budget_score": 60, "intent_score": 60, "urgency_score": 60,
        "agent_fit_score": 60, "reachability_score": 60, "evidence_score": 60,
    }).json()["data"]

    client.post(f"/api/v1/opportunities/{opp['id']}/review", json={
        "action": "edit", "note": "调整证据分", "updates": {"evidence_score": 80},
    })
    logs = client.get("/api/v1/logs/audit", params={"page_size": 30}).json()["data"]["items"]
    entry = next(x for x in logs if x["action"] == "REVIEW" and x["entity_id"] == opp["id"])
    payload = entry["payload_json"]
    assert payload["before"]["evidence_score"] == 60
    assert payload["after"]["evidence_score"] == 80
    assert payload["before"]["stage"] == "NEW"
    assert payload["after"]["stage"] == "NEW"
    assert payload["note"] == "调整证据分"


def test_ingest_records_reliability_snapshot_and_rejects_empty_page(client, monkeypatch):
    suffix = uuid.uuid4().hex[:6]

    def _fake_fetch(url: str) -> FetchedPage:
        html = f"""
        <html><head><title>快照测试{suffix}</title>
        <meta property="og:site_name" content="快照企业{suffix}"/></head>
        <body><main><p>快照测试{suffix} 正在招聘销售经理。</p></main></body></html>
        """
        return extractor.parse_html(url, url, 200, "text/html; charset=utf-8", html)

    monkeypatch.setattr(extractor, "fetch_public_page", _fake_fetch)
    resp = client.post("/api/v1/ingest/url", json={"url": f"https://snapshot-test-{suffix}.example.com/"})
    assert resp.status_code == 200
    record = client.get(f"/api/v1/source-records/{resp.json()['data']['source_record_id']}").json()["data"]
    # 手动URL分析来源默认 C 级 → 快照必须一致，验证状态初始未验证
    assert record["source_reliability"] == "C"
    assert record["verification_status"] == "UNVERIFIED"

    # 空正文页面：内容非空检查拒绝入库
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: extractor.parse_html(url, url, 200, "text/html", EMPTY_HTML))
    empty = client.post("/api/v1/ingest/url", json={"url": f"https://empty-page-{suffix}.example.com/"})
    assert empty.status_code == 422
    assert "正文" in empty.json()["detail"]


def test_full_traceable_chain_from_signal_to_url(client):
    """核心验收：Signal → Evidence → SourceRecord → 原始 URL 链路不能断。"""
    company, signal, record, source = _setup_company_signal(client)
    sig_detail = client.get(f"/api/v1/signals/{signal['id']}").json()["data"]
    assert sig_detail["evidence"]["source_record_id"] == record["id"]
    assert sig_detail["evidence"]["url"] == "https://chain-test.example.com/news/1"
    assert sig_detail["evidence"]["source_name"] == source["name"]
    assert sig_detail["evidence"]["reliability_grade"] == "A"

    rec_detail = client.get(f"/api/v1/source-records/{record['id']}").json()["data"]
    assert rec_detail["url"] == "https://chain-test.example.com/news/1"
    assert rec_detail["content_hash"]
    assert rec_detail["source"]["reliability_grade"] == "A"
