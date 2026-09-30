"""RSSCollector 测试（Mock feed 内容，不访问公网）。"""
from datetime import timezone

import pytest

from app.collectors.rss import RSSCollector

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>测试订阅</title>
  <item>
    <title>企业A完成融资</title>
    <link>https://news.example.com/a</link>
    <description>企业A宣布完成B轮融资1亿元。</description>
    <pubDate>Mon, 28 Sep 2026 08:00:00 GMT</pubDate>
    <author>编辑甲</author>
  </item>
  <item>
    <title>企业B扩产</title>
    <link>https://news.example.com/b?utm_source=feed</link>
    <description>企业B宣布新建产线。</description>
    <pubDate>Tue, 29 Sep 2026 09:30:00 GMT</pubDate>
  </item>
  <item><title>无链接条目</title></item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom测试</title>
  <entry>
    <title>政府发布采购公告</title>
    <link href="https://gov.example.com/notice/1"/>
    <updated>2026-09-29T10:00:00Z</updated>
    <content type="html">某单位公开采购信息系统服务。</content>
  </entry>
</feed>"""


class FakeFeedSource:
    id = "src_test_rss"
    base_url = "https://feeds.example.com/rss"
    reliability_grade = "B"
    config_json = {}


@pytest.fixture()
def mock_feed(monkeypatch):
    def _fake(self):
        return RSS_XML
    monkeypatch.setattr(RSSCollector, "_fetch_feed", _fake)


@pytest.fixture()
def mock_atom(monkeypatch):
    def _fake(self):
        return ATOM_XML
    monkeypatch.setattr(RSSCollector, "_fetch_feed", _fake)


def test_rss_entries_parsed(mock_feed):
    collector = RSSCollector(FakeFeedSource)
    items = collector.build_records()
    assert len(items) == 2  # 无链接条目被跳过
    first = items[0]
    assert first.title == "企业A完成融资"
    assert "B轮融资" in first.raw_text
    assert first.published_at is not None and first.published_at.tzinfo == timezone.utc
    assert first.author == "编辑甲"
    assert first.parse_status == "OK"


def test_rss_canonical_url_strips_tracking(mock_feed):
    collector = RSSCollector(FakeFeedSource)
    items = collector.build_records()
    second = items[1]
    assert second.canonical_url == "https://news.example.com/b"  # utm 参数已去除


def test_atom_entry_parsed_with_relative_link(mock_atom):
    collector = RSSCollector(FakeFeedSource)
    items = collector.build_records()
    assert len(items) == 1
    assert items[0].url == "https://gov.example.com/notice/1"
    assert "采购" in items[0].raw_text


def test_rss_feed_failure_marks_failed(monkeypatch):
    def _fail(self):
        raise RuntimeError("feed unreachable")
    monkeypatch.setattr(RSSCollector, "_fetch_feed", _fail)
    collector = RSSCollector(FakeFeedSource)
    items = collector.build_records()
    assert len(items) == 1
    assert items[0].parse_status == "FAILED"
    assert collector.run_log[0]["status"] == "FAILED"
