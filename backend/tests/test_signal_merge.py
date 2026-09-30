"""多来源合并测试：官网 + 权威新闻确认同一事件 → 一个 Signal + 多 Evidence。"""
import uuid

from app.analyzers.extractor import run_extractor
from app.db.session import SessionLocal
from app.models.signal import Signal, SignalCandidate, SignalEvidence
from app.models.source import SourceRecord


def _mk_record(client, company_id, *, name, grade, url_path, raw):
    suffix = uuid.uuid4().hex[:5]
    src = client.post("/api/v1/sources", json={"name": f"{name}{suffix}", "source_type": "OFFICIAL_WEBSITE" if grade == "A" else "NEWS", "base_url": f"https://m{suffix}.example.com", "reliability_grade": grade, "reliability_score": 95 if grade == "A" else 80}).json()["data"]
    return client.post(f"/api/v1/sources/{src['id']}/records", json={"company_id": company_id, "url": f"https://m{suffix}.example.com/{url_path}", "title": "公告", "raw_text": raw}).json()["data"]


def test_multi_source_merge_into_single_signal(client):
    """同一事件被官网（A）与新闻（B）先后确认 → 合并为一个 Signal，证据来自两个记录。
    流程：来源1 产出候选 → 人工审核成为正式 Signal → 来源2 同事件自动并入（多 Evidence）。
    """
    suffix = uuid.uuid4().hex[:5]
    company = client.post("/api/v1/companies", json={"company_name": f"合并企业{suffix}", "domain": f"merge-{suffix}.example.com"}).json()["data"]
    raw = "公司今日公告：设立海外子公司，拓展欧洲市场业务。"
    r1 = _mk_record(client, company["id"], name="官网", grade="A", url_path="official", raw=raw)
    r2 = _mk_record(client, company["id"], name="新闻", grade="B", url_path="news", raw=raw)

    with SessionLocal() as db:
        rec1, rec2 = db.get(SourceRecord, r1["id"]), db.get(SourceRecord, r2["id"])
        rec1.company_resolve_status = "EXACT"
        rec2.company_resolve_status = "EXACT"
        db.commit()
        run_extractor(db, rec1)
        # 候选审核 → 正式 Signal
        from app.models.signal import SignalCandidate
        cand = db.query(SignalCandidate).filter(SignalCandidate.source_record_id == rec1.id).first()
        assert cand is not None
        approve = client.post(f"/api/v1/signal-candidates/{cand.id}/approve", json={"note": "官网事实"})
        assert approve.status_code == 200
        run_extractor(db, rec2)

        signals = db.query(Signal).filter(Signal.company_id == company["id"], Signal.signal_type == "OVERSEAS_EXPANSION").all()
        assert len(signals) == 1
        signal = signals[0]
        assert signal.created_by == "MERGE"
        assert signal.last_seen_at is not None
        evidences = db.query(SignalEvidence).filter(SignalEvidence.signal_id == signal.id).all()
        assert len(evidences) == 2  # 官网 + 新闻 两条证据
        assert {e.source_record_id for e in evidences} == {rec1.id, rec2.id}
        # 合并后候选记录标注 MERGED
        merged = db.query(SignalCandidate).filter(SignalCandidate.status == "MERGED", SignalCandidate.signal_id == signal.id).count()
        assert merged >= 1


def test_merge_boosts_confidence(client):
    """多来源确认 → 证据相互印证，置信度适度提升。"""
    suffix = uuid.uuid4().hex[:5]
    company = client.post("/api/v1/companies", json={"company_name": f"提升企业{suffix}", "domain": f"boost-{suffix}.example.com"}).json()["data"]
    raw = "公司今日公告：设立海外子公司，拓展欧洲市场业务。"
    r1 = _mk_record(client, company["id"], name="源甲", grade="A", url_path="a", raw=raw)
    r2 = _mk_record(client, company["id"], name="源乙", grade="B", url_path="b", raw=raw)
    with SessionLocal() as db:
        rec1, rec2 = db.get(SourceRecord, r1["id"]), db.get(SourceRecord, r2["id"])
        rec1.company_resolve_status = "EXACT"
        rec2.company_resolve_status = "EXACT"
        db.commit()
        run_extractor(db, rec1)
        from app.models.signal import SignalCandidate
        cand = db.query(SignalCandidate).filter(SignalCandidate.source_record_id == rec1.id).first()
        client.post(f"/api/v1/signal-candidates/{cand.id}/approve")
        signals = db.query(Signal).filter(Signal.company_id == company["id"]).all()
        conf_before = signals[0].confidence if signals else None
        run_extractor(db, rec2)
        signals2 = db.query(Signal).filter(Signal.company_id == company["id"]).all()
        assert len(signals2) == len(signals)  # 未新建
        assert signals2[0].confidence >= conf_before  # 提升或持平
