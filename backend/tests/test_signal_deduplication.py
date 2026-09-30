"""Signal 去重测试：指纹、时间窗口、同事件不重复创建。"""
import uuid
from datetime import datetime, timedelta, timezone

from app.analyzers.dedup import compute_signal_fingerprint, event_time_bucket, find_duplicate_signal, normalize_event_text


def test_normalize_event_text_ignores_noise():
    a = normalize_event_text("公司 招聘、海外销售 10名！")
    b = normalize_event_text("公司招聘海外销售 25名")
    assert a == b  # 数字与标点差异不影响指纹（同质事件）


def test_fingerprint_stable_and_sensitive():
    fp1 = compute_signal_fingerprint("cmp1", "SALES_HIRING", "招聘海外销售10名", datetime(2026, 9, 28, tzinfo=timezone.utc))
    fp2 = compute_signal_fingerprint("cmp1", "SALES_HIRING", "招聘海外销售12名", datetime(2026, 9, 29, tzinfo=timezone.utc))
    fp3 = compute_signal_fingerprint("cmp2", "SALES_HIRING", "招聘海外销售10名", datetime(2026, 9, 28, tzinfo=timezone.utc))
    fp4 = compute_signal_fingerprint("cmp1", "FUNDING", "招聘海外销售10名", datetime(2026, 9, 28, tzinfo=timezone.utc))
    assert fp1 == fp2  # 同企业同类型同事件窗口（数量差异归一）
    assert fp1 != fp3  # 不同企业
    assert fp1 != fp4  # 不同类型


def test_time_bucket_respects_window():
    # 14 天窗口：相邻日期同桶；跨窗口不同桶（不永久合并）
    a = event_time_bucket(datetime(2026, 9, 1, tzinfo=timezone.utc), None, 14)
    b = event_time_bucket(datetime(2026, 9, 10, tzinfo=timezone.utc), None, 14)
    c = event_time_bucket(datetime(2026, 9, 25, tzinfo=timezone.utc), None, 14)
    assert a == b
    assert a != c


def test_same_event_not_duplicated_across_runs(client):
    """同一企业同一事件二次分析 → 不重复创建正式 Signal（candidate 标 MERGED）。"""
    from app.analyzers.extractor import run_extractor
    from app.db.session import SessionLocal
    from app.models.signal import Signal, SignalCandidate
    from app.models.source import SourceRecord

    suffix = uuid.uuid4().hex[:5]
    raw = "公司公告：本季度招聘海外销售经理10名。"
    company = client.post("/api/v1/companies", json={"company_name": f"去重企业{suffix}", "domain": f"dedup-{suffix}.example.com"}).json()["data"]
    src = client.post("/api/v1/sources", json={"name": f"去重源{suffix}", "source_type": "OFFICIAL_WEBSITE", "base_url": f"https://dedup-{suffix}.example.com", "reliability_grade": "A", "reliability_score": 95}).json()["data"]
    r1 = client.post(f"/api/v1/sources/{src['id']}/records", json={"company_id": company["id"], "url": f"https://dedup-{suffix}.example.com/news", "title": "招聘公告", "raw_text": raw}).json()["data"]
    r2 = client.post(f"/api/v1/sources/{src['id']}/records", json={"company_id": company["id"], "url": f"https://dedup-{suffix}.example.com/news-mirror", "title": "招聘公告（转载）", "raw_text": raw}).json()["data"]

    with SessionLocal() as db:
        rec1, rec2 = db.get(SourceRecord, r1["id"]), db.get(SourceRecord, r2["id"])
        rec1.company_resolve_status = "EXACT"
        rec2.company_resolve_status = "EXACT"
        db.commit()
        run_extractor(db, rec1)
        run_extractor(db, rec2)
        signals = db.query(Signal).filter(Signal.signal_type == "SALES_HIRING", Signal.company_id == company["id"]).all()
        assert len(signals) <= 1  # 同事件只有一个正式 Signal
        merged = db.query(SignalCandidate).filter(SignalCandidate.source_record_id == rec2.id, SignalCandidate.status == "MERGED").all()
        assert len(merged) >= 1  # 第二来源并入既有 Signal


def test_find_duplicate_none_for_new_fingerprint():
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        assert find_duplicate_signal(db, "nonexistent" + uuid.uuid4().hex[:8]) is None
