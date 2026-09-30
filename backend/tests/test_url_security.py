"""URL 安全与规范化测试（T03：canonicalize_url + SSRF 强化）。"""
import pytest

from app.collectors.urlutils import canonicalize_url
from app.services.extractor import URLSafetyError, validate_public_url


# ---------------------------------------------------------------------------
# canonicalize_url：去噪不误并
# ---------------------------------------------------------------------------

def test_canonical_strips_utm_and_fragment():
    assert canonicalize_url("https://Example.com/a/?utm_source=x&utm_campaign=y#g1") == "https://example.com/a"


def test_canonical_keeps_semantic_query():
    assert canonicalize_url("https://example.com/search?q=ai&page=2") == "https://example.com/search?q=ai&page=2"


def test_canonical_www_and_slashes():
    assert canonicalize_url("http://WWW.Example.com//news///") == "http://example.com/news"
    assert canonicalize_url("https://www.example.com") == "https://example.com/"


def test_canonical_different_pages_not_merged():
    assert canonicalize_url("https://example.com/a?id=1") != canonicalize_url("https://example.com/a?id=2")


def test_canonical_keeps_non_default_port():
    assert canonicalize_url("https://example.com:8443/x") == "https://example.com:8443/x"


# ---------------------------------------------------------------------------
# SSRF：内网 / 保留地址（fetch 层校验）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "http://localhost", "http://127.0.0.1", "http://0.0.0.0", "http://[::1]",
    "http://10.0.0.5", "http://172.31.255.1", "http://192.168.0.9",
    "http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "ftp://x.example.com/f",
])
def test_ssrf_blocked_at_fetch_layer(bad, monkeypatch):
    """fetch_public_page 必须在发起请求前完成校验：内网请求不触达 socket。"""
    import socket as _socket

    def _no_dns(host, port=None):
        raise AssertionError(f"SSRF 防护失效：对 {bad} 发起了 DNS/连接")

    monkeypatch.setattr(_socket, "getaddrinfo", _no_dns)
    from app.services import extractor
    with pytest.raises((URLSafetyError, AssertionError)):
        extractor.fetch_public_page(bad)


def test_ssrrf_private_dns_name_blocked(monkeypatch):
    import socket as _socket

    def _fake_dns(host, port=None):
        return [(_socket.AF_INET, None, None, "", ("192.168.1.50", 0))]

    monkeypatch.setattr(_socket, "getaddrinfo", _fake_dns)
    from app.services import extractor
    with pytest.raises(URLSafetyError):
        extractor.fetch_public_page("https://internal-looking.example.com/")
