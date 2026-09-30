"""CollectorAdapter 注册表与接口测试。"""
import pytest

from app.collectors import available_collectors, get_adapter
from app.collectors.base import CollectedItem, CollectorAdapter


class _Dummy(CollectorAdapter):
    collector_type = "dummy_for_test"

    def validate_config(self):
        if not self.config.get("url"):
            raise ValueError("需要 url")

    def fetch(self):
        return []


def test_registry_contains_builtin_collectors():
    collectors = available_collectors()
    assert "web_page" in collectors
    assert "rss" in collectors
    assert "manual_url" in collectors


def test_get_adapter_unknown_type_rejected():
    class FakeSource:
        base_url = "https://x.example.com"
        config_json = {}
    with pytest.raises(ValueError, match="未知采集器类型"):
        get_adapter("not_exists", FakeSource())


def test_get_adapter_validates_config():
    class FakeSource:
        base_url = None
        config_json = {}
    with pytest.raises(ValueError, match="base_url"):
        get_adapter("web_page", FakeSource())
    adapter = get_adapter("web_page", FakeSource, {"url": "https://a.example.com"})
    assert adapter.collector_type == "web_page"


def test_collected_item_hash_stable_and_content_sensitive():
    a = CollectedItem(url="https://x.example.com/p?utm_source=t", canonical_url="https://x.example.com/p", title="T", raw_text="正文 A")
    b = CollectedItem(url="https://x.example.com/p", canonical_url="https://x.example.com/p", title="T", raw_text="正文 A")
    assert a.content_hash() == b.content_hash()  # 与 url 噪声无关，内容一致即同 hash
    c = CollectedItem(url="https://x.example.com/p", canonical_url="https://x.example.com/p", title="T", raw_text="正文 B")
    assert a.content_hash() != c.content_hash()


def test_adapter_run_log_records_entries():
    class FakeSource:
        base_url = None
    adapter = get_adapter("manual_url", FakeSource, {"url": "https://a.example.com"})
    adapter.log("https://a.example.com", "HTTP_200", 12)
    adapter.log("https://b.example.com", "FAILED", error="x")
    assert len(adapter.run_log) == 2
    assert adapter.run_log[0]["latency_ms"] == 12
    assert adapter.run_log[1]["error"] == "x"
