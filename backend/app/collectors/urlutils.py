"""URL 规范化：同页识别与版本对比的基础。

原则：只去除「不影响页面内容」的噪声（utm 等跟踪参数、fragment、大小写、重复斜杠）；
不能把不同真实页面错误合并（保留 path/query 的语义差异）。
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# 常见跟踪/会话参数：去除后不影响内容
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "from", "spm", "share_", "scene")
_TRACKING_EXACT = {"yclid", "msclkid", "_hsenc", "_hsmi", "mc_cid", "mc_eid", "igshid"}


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "http").lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    # 统一 www 前缀（www.example.com 与 example.com 视为同站同页）
    if host.startswith("www."):
        host = host[4:]

    # 规范化 path：合并重复斜杠、去尾部斜杠（根路径除外）
    path = parsed.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # 过滤跟踪参数；保持原有参数顺序
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not (k.lower() in _TRACKING_EXACT or any(k.lower().startswith(p) for p in _TRACKING_PREFIXES))
    ]
    query = urlencode(query_pairs)

    port = ""
    if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
        port = f":{parsed.port}"
    return urlunparse((scheme, f"{host}{port}", path, "", query, ""))
