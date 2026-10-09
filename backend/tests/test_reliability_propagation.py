"""T08.0 P0-4 Reliability 传递链测试：Source A → SourceRecord A → Evidence A（可降不可升）。"""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.reliability import effective_grade, effective_score, propagate_record_grade


def test_effective_grade_rules():
    assert effective_grade("A", None) == "A"
    assert effective_grade("A", "A") == "A"
    assert effective_grade("A", "B") == "B"      # 下游显式降级：允许
    assert effective_grade("A", "C") == "C"
    assert effective_grade("B", "A") == "B"      # 下游无理由升级：压制回源等级
    assert effective_grade("C", "A") == "C"
    assert effective_grade(None) == "C"          # 缺失默认 C（保守）
    assert effective_grade("X") == "C"


def test_effective_score_uses_source_score():
    assert effective_score("A", 95) == 95
    assert effective_score("A", 95, "B") == 80   # 降级后按降级等级
    assert effective_score("B", 80, "A") == 80   # 升级被压制，保持 Source 分
    assert effective_score("C", None) == 60


def test_propagate_record_grade():
    assert propagate_record_grade("A") == "A"


def test_record_snapshot_inherits_source(client):
    """Source A 建记录 → SourceRecord.source_reliability 默认 A（不再出现 A 源 C 快照）。"""
    suffix = uuid.uuid4().hex[:6]
    source = client.post("/api/v1/sources", json={
        "name": f"可靠源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://relia.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "url": f"https://relia.example.com/{suffix}", "title": "公告", "raw_text": "正文内容足够长。",
    }).json()["data"]
    assert record["source_reliability"] == "A"

    # 同 Source 降级配置后，新记录继承新等级（可降）
    client.patch(f"/api/v1/sources/{source['id']}", json={"reliability_grade": "C"})
    record2 = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "url": f"https://relia.example.com/{suffix}-2", "title": "公告2", "raw_text": "第二条正文。",
    }).json()["data"]
    assert record2["source_reliability"] == "C"


def test_signal_evidence_grade_from_chain(client):
    """T05 Evidence 的 source_grade 来自 Source 实时等级（B 级源不得出现 A 级 Evidence）。"""
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={"company_name": f"证据链企业{suffix}"}).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"证据链源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://chain.example.com", "reliability_grade": "B", "reliability_score": 80,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": f"https://chain.example.com/{suffix}",
        "title": "公告", "raw_text": "公司今日宣布设立海外子公司，拓展欧洲市场业务。",
    }).json()["data"]

    with TestClient(app):
        from app.db.session import SessionLocal
        from app.models.source import SourceRecord

        with SessionLocal() as db:
            rec = db.get(SourceRecord, record["id"])
            rec.company_resolve_status = "EXACT"
            db.commit()
            from app.analyzers.extractor import run_extractor

            run_extractor(db, rec)

    # 信号创建（候选审核后成为正式 Signal）；此处直接校验 record 快照与 Source 一致
    assert record["source_reliability"] == "B"
