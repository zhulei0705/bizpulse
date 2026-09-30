"""去重与版本机制测试（persist_collected）。"""
import uuid

import pytest
from sqlalchemy import select

from app.collectors.base import CollectedItem
from app.collectors.urlutils import canonicalize_url
from app.models.source import Source, SourceRecord
from app.services.collection_engine import persist_collected


@pytest.fixture()
def web_source(client):
    suffix = uuid.uuid4().hex[:6]
    source = client.post("/api/v1/sources", json={
        "name": f"版本测试源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://ver-test.example.com", "reliability_grade": "A", "reliability_score": 95,
        "collector_type": "web_page", "config_json": {},
    }).json()["data"]
    db_source = None
    return source


def _make_db_session():
    from app.db.session import SessionLocal
    return SessionLocal()


def _item(text: str, url="https://ver-test.example.com/news/1", title="公告"):
    return CollectedItem(url=url, canonical_url=canonicalize_url(url), title=title, raw_text=text, http_status=200, content_type="text/html")


def test_same_content_not_duplicated(client, web_source):
    with _make_db_session() as db:
        source = db.get(Source, web_source["id"])
        r1, o1 = persist_collected(db, source, _item("第一版正文内容"))
        r2, o2 = persist_collected(db, source, _item("第一版正文内容"))
        db.commit()
        assert o1 == "CREATED" and o2 == "SKIPPED_UNCHANGED"
        assert r1.id == r2.id
        assert r2.checked_at is not None
        total = db.scalars(select(SourceRecord).where(SourceRecord.source_id == source.id)).all()
        assert len(total) == 1  # 未创建第二条


def test_changed_content_creates_version_history(client, web_source):
    with _make_db_session() as db:
        source = db.get(Source, web_source["id"])
        r1, o1 = persist_collected(db, source, _item("第一版：招聘3人"))
        r2, o2 = persist_collected(db, source, _item("第二版：招聘5人"))
        db.commit()
        assert o1 == "CREATED" and o2 == "UPDATED_VERSION"
        assert r2.parent_record_id == r1.id
        assert r2.version_number == 2
        assert r1.is_latest is False and r2.is_latest is True
        # 两个版本都保留（历史可追溯）
        versions = db.scalars(select(SourceRecord).where(SourceRecord.source_id == source.id)).all()
        assert len(versions) == 2


def test_tracking_params_do_not_create_duplicate(client, web_source):
    with _make_db_session() as db:
        source = db.get(Source, web_source["id"])
        r1, o1 = persist_collected(db, source, _item("同内容", url="https://ver-test.example.com/news/2"))
        r2, o2 = persist_collected(db, source, _item("同内容", url="https://ver-test.example.com/news/2?utm_source=newsletter"))
        db.commit()
        assert o1 == "CREATED"
        assert o2 == "SKIPPED_UNCHANGED"  # canonical_url 相同 + 内容相同 → 去重
        assert r1.id == r2.id


def test_failed_parse_saved_as_failed_record(client, web_source):
    failed = CollectedItem(url="https://ver-test.example.com/empty", canonical_url=canonicalize_url("https://ver-test.example.com/empty"), parse_status="FAILED", error_message="页面无可提取正文内容")
    with _make_db_session() as db:
        source = db.get(Source, web_source["id"])
        record, outcome = persist_collected(db, source, failed)
        db.commit()
        assert outcome == "FAILED"
        assert record.parse_status == "FAILED"
        assert record.error_message == "页面无可提取正文内容"
