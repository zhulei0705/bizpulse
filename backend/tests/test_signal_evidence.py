"""Evidence 机制测试：原文可寻校验、offset 高亮、inference 不得成为证据。"""
import uuid

from app.analyzers.extractor import _evidence_in_source


def test_evidence_in_source_exact_and_flattened():
    source = "公司计划于2026年第四季度新增100名销售人员，覆盖华东市场。"
    assert _evidence_in_source("新增100名销售人员", source) is True
    assert _evidence_in_source("公司计划于2026年第四季度\n新增100名销售人员", "公司计划于2026年第四季度 新增100名销售人员。") is True  # 换行容忍
    assert _evidence_in_source("企业正在大规模扩张销售团队", source) is False  # AI 改写句不在原文
    assert _evidence_in_source(None, source) is False
    assert _evidence_in_source("   ", source) is False


def test_candidate_evidence_offsets_point_into_raw_text(client):
    """候选 offset 必须指向原文真实位置（可用于前端高亮）。"""
    suffix = uuid.uuid4().hex[:5]
    raw = "企业简介。本公司正在招聘海外销售经理8名，base上海。欢迎加入。"
    company = client.post("/api/v1/companies", json={"company_name": f"证据企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={"name": f"证据源{suffix}", "source_type": "OFFICIAL_WEBSITE", "base_url": f"https://ev-{suffix}.example.com", "reliability_grade": "A", "reliability_score": 95}).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={"company_id": company["id"], "url": f"https://ev-{suffix}.example.com/jobs", "title": "招聘", "raw_text": raw}).json()["data"]
    client.post(f"/api/v1/source-records/{record['id']}/analyze-signals")
    candidates = client.get("/api/v1/signal-candidates", params={"source_record_id": record["id"]}).json()["data"]["items"]
    assert candidates
    for c in candidates:
        if c["start_offset"] is not None:
            assert raw[c["start_offset"]:c["end_offset"]].strip() == (c["evidence_text"] or "").strip()


def test_approved_signal_has_original_text_evidence(client):
    """正式 Signal 的 Evidence 必须是原文引用（evidence_type=ORIGINAL_TEXT），带 offset。"""
    suffix = uuid.uuid4().hex[:5]
    raw = "官方新闻：公司完成B轮融资2亿元，由知名机构领投。"
    company = client.post("/api/v1/companies", json={"company_name": f"证据企业B{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={"name": f"证据源B{suffix}", "source_type": "OFFICIAL_NEWS", "base_url": f"https://evb-{suffix}.example.com", "reliability_grade": "A", "reliability_score": 95}).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={"company_id": company["id"], "url": f"https://evb-{suffix}.example.com/news", "title": "融资新闻", "raw_text": raw}).json()["data"]
    client.post(f"/api/v1/source-records/{record['id']}/analyze-signals")
    cand = next(c for c in client.get("/api/v1/signal-candidates", params={"source_record_id": record["id"]}).json()["data"]["items"] if c["candidate_type"] == "FUNDING")
    approve = client.post(f"/api/v1/signal-candidates/{cand['id']}/approve", json={"note": "事实清楚"})
    assert approve.status_code == 200
    signal_id = approve.json()["data"]["signal_id"]
    evidences = client.get(f"/api/v1/signals/{signal_id}/evidences").json()["data"]["items"]
    assert len(evidences) >= 1
    ev = evidences[0]
    assert ev["evidence_type"] == "ORIGINAL_TEXT"
    assert ev["quoted_text"] and "融资" in ev["quoted_text"]
    assert ev["url"].startswith("https://evb-")
    # 信号详情：fact 基于原文、inference 与事实分离
    detail = client.get(f"/api/v1/signals/{signal_id}").json()["data"]
    assert detail["fact_summary"]
    assert detail["status"] == "APPROVED"


def test_manual_signal_requires_evidence_url(client):
    """人工创建 Signal 仍须关联真实证据（T02 规则在 T04 继续生效）。"""
    suffix = uuid.uuid4().hex[:5]
    company = client.post("/api/v1/companies", json={"company_name": f"人工信号企业{suffix}"}).json()["data"]
    resp = client.post("/api/v1/signals", json={
        "company_id": company["id"], "signal_type": "PARTNERSHIP", "title": "无证据信号",
    })
    assert resp.status_code == 422  # 无 source_record_id / evidence_url 拒绝
