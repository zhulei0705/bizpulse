"""WebPageCollector 测试（Mock extractor.fetch_public_page，不访问公网）。"""
import pytest

from app.collectors import get_adapter
from app.collectors.urlutils import canonicalize_url
from app.services import extractor

HTML = """
<html><head><title>测试企业 - 招聘</title>
<meta property="og:site_name" content="测试企业"/></head>
<body><main><p>测试企业正在招聘海外销售经理并扩大产能。</p></main></body></html>
"""


class FakeSource:
    id = "src_test_web"
    base_url = "https://www.test-web-example.com"
    reliability_grade = "B"
    config_json = {}


@pytest.fixture()
def mock_page(monkeypatch):
    calls = []

    def _fake(url):
        calls.append(url)
        return extractor.parse_html(url, url, 200, "text/html; charset=utf-8", HTML)

    monkeypatch.setattr(extractor, "fetch_public_page", _fake)
    return calls


def test_web_collector_fetch_and_fields(mock_page):
    adapter = get_adapter("web_page", FakeSource)
    items = adapter.build_records()
    assert len(items) == 1
    item = items[0]
    assert item.parse_status == "OK"
    assert item.title == "测试企业 - 招聘"
    assert "海外销售经理" in item.raw_text
    assert item.canonical_url == canonicalize_url(FakeSource.base_url)
    assert item.extra["og_site_name"] == "测试企业"
    assert adapter.run_log and adapter.run_log[0]["status"] == "HTTP_200"


def test_web_collector_saves_raw_html(mock_page):
    from app.collectors import web as webmod
    from app.core.config import BASE_DIR
    adapter = get_adapter("web_page", FakeSource)
    original = webmod.WebPageCollector._save_raw_html
    saved = {}

    def _fake_save(self, hint, url, html):
        path = original(self, hint, url, html)
        saved["path"] = path
        return path

    webmod.WebPageCollector._save_raw_html = _fake_save
    try:
        items = adapter.build_records()
        assert items[0].extra["raw_html_path"].startswith("data")
        assert "raw" in items[0].extra["raw_html_path"]
    finally:
        webmod.WebPageCollector._save_raw_html = original
    # 清理测试写入的 raw 目录
    import shutil
    raw_dir = BASE_DIR / "data" / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir, ignore_errors=True)


def test_web_collector_empty_page_marks_failed(monkeypatch):
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: extractor.parse_html(url, url, 200, "text/html", "<html><body>  </body></html>"))
    adapter = get_adapter("web_page", FakeSource)
    items = adapter.build_records()
    assert items[0].parse_status == "FAILED"
    assert "正文" in items[0].error_message


def test_web_collector_network_failure_returns_failed_item(monkeypatch):
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: (_ for _ in ()).throw(RuntimeError("connection refused")))
    adapter = get_adapter("web_page", FakeSource, {"max_retries": 0})
    items = adapter.build_records()
    assert items[0].parse_status == "FAILED"
    assert "connection refused" in items[0].error_message


def test_manual_url_collector_requires_url():
    with pytest.raises(ValueError, match="config.url"):
        get_adapter("manual_url", FakeSource)
