"""SignalExtractor 编排测试：record→候选→审核/自动批准、幂等、LLM 未配置不阻塞。"""
import uuid

import pytest


def _make_record(client, raw_text: str, *, grade="A", company=True, source_type="OFFICIAL_WEBSITE"):
    suffix = uuid.uuid4().hex[:6]
    company_id = None
    if company:
        company_id = client.post("/api/v1/companies", json={"company_name": f"提取企业{suffix}"}).json()["data"]["id"]
    source = client.post("/api/v1/sources", json={
        "name": f"提取源{suffix}", "source_type": source_type, "base_url": f"https://ext-{suffix}.example.com",
        "reliability_grade": grade, "reliability_score": 95 if grade == "A" else 60,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company_id, "url": f"https://ext-{suffix}.example.com/news", "title": "企业动态", "raw_text": raw_text,
    }).json()["data"]
    return record["id"], source["id"]


def _session():
    from app.db.session import SessionLocal
    return SessionLocal()


def test_extractor_creates_candidates_and_signals(client):
    from app.analyzers.extractor import run_extractor
    from app.models.signal import Signal, SignalCandidate
    from app.models.source import SourceRecord

    text = "公司官网公告：本季度招聘海外销售经理10名，并宣布完成A轮融资。"
    record_id, _ = _make_record(client, text)
    with _session() as db:
        record = db.get(SourceRecord, record_id)
        record.company_resolve_status = "HIGH_CONFIDENCE"
        db.commit()
        stats = run_extractor(db, record)
        assert stats.candidates_detected >= 2  # SALES_HIRING + FUNDING
        candidates = db.query(SignalCandidate).filter(SignalCandidate.source_record_id == record_id).all()
        assert all(c.final_confidence > 0 for c in candidates)
        # FUNDING review_always=True → 即使高分也 REVIEW_REQUIRED（人工确认融资类敏感事件）
        funding = next((c for c in candidates if c.candidate_type == "FUNDING"), None)
        if funding:
            assert funding.status == "REVIEW_REQUIRED"
        # A 级 + 明确证据 + 高分 → SALES_HIRING 可自动批准
        sales = next(c for c in candidates if c.candidate_type == "SALES_HIRING")
        assert sales.status in {"APPROVED", "REVIEW_REQUIRED"}
        if sales.status == "APPROVED":
            assert sales.signal_id
            signal = db.get(Signal, sales.signal_id)
            assert signal.status == "APPROVED"
            assert signal.fact_summary and signal.first_seen_at


def test_extractor_idempotent_when_hash_unchanged(client):
    from app.analyzers.extractor import run_extractor
    from app.models.source import SourceRecord

    record_id, _ = _make_record(client, "公司正在招聘海外销售人员5名。")
    with _session() as db:
        record = db.get(SourceRecord, record_id)
        first = run_extractor(db, record)
        second = run_extractor(db, record)
        assert first.candidates_detected >= 1
        assert second.candidates_detected == 0  # hash 未变 → 不重复分析
        assert any("跳过" in e or "未变化" in e for e in second.errors)


def test_extractor_llm_not_configured_still_works(client):
    """LLM 未配置：Rule Engine 仍运行产出候选，流程不失败。"""
    from app.analyzers.extractor import run_extractor
    from app.models.source import SourceRecord

    record_id, _ = _make_record(client, "企业宣布设立海外子公司，拓展欧洲业务。")
    with _session() as db:
        record = db.get(SourceRecord, record_id)
        stats = run_extractor(db, record)
        assert stats.llm_used is False
        assert stats.candidates_detected >= 1
        assert stats.errors == []


def test_extractor_via_api(client):
    record_id, _ = _make_record(client, "公司发布全新产品平台，并启动数字化转型。")
    resp = client.post(f"/api/v1/source-records/{record_id}/analyze-signals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["candidates_detected"] >= 1
    assert data["llm_used"] is False
    # 候选列表可查
    listing = client.get("/api/v1/signal-candidates").json()["data"]
    assert listing["total"] >= 1
    item = listing["items"][0]
    assert item["evidence_text"] and item["final_confidence"] > 0
