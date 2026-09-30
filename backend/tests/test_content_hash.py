"""content_hash 测试：规范化、去重键、版本判断。"""
from app.collectors.base import CollectedItem
from app.collectors.urlutils import canonicalize_url


def _item(text, title="T", url="https://x.example.com/p"):
    return CollectedItem(url=url, canonical_url=canonicalize_url(url), title=title, raw_text=text)


def test_hash_ignores_url_tracking_noise():
    a = _item("同一段正文", url="https://x.example.com/p?utm_source=mail")
    b = _item("同一段正文", url="https://x.example.com/p")
    assert a.content_hash() == b.content_hash()


def test_hash_changes_when_text_changes():
    assert _item("版本一").content_hash() != _item("版本二").content_hash()


def test_hash_changes_when_title_changes():
    assert _item("正文", title="A").content_hash() != _item("正文", title="B")


def test_hash_stable_across_calls():
    item = _item("稳定性正文")
    assert item.content_hash() == item.content_hash()


def test_hash_of_empty_content_is_valid_sha256():
    import re
    digest = _item(None, title=None).content_hash()
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
