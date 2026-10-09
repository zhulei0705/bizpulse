"""T10-C1：许可、robots、DNS 固定与有界 HTTP；不使用环境代理或 Cookie。"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser

from app.services.extractor import URLSafetyError

USER_AGENT = "BizPulseBot/0.1"
_LOCK = threading.Lock()
_HTTP_SLOT = threading.RLock()  # V1 单进程全通道并发上限 1；部署多 worker 前需共享限流。
_LAST: dict[str, float] = {}


class CrawlStopped(URLSafetyError):
    """安全/许可异常必须停止，不能退回不受保护的采集器。"""


def check_url(url: str, domains: set[str]) -> tuple[str, int]:
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        port = p.port or (443 if p.scheme == "https" else 80)
    except ValueError:
        raise CrawlStopped("INVALID_URL") from None
    if p.scheme not in {"https", "http"} or p.username or p.password or not host:
        raise CrawlStopped("URL_SCHEME_OR_CREDENTIALS")
    if host not in domains or port != (443 if p.scheme == "https" else 80):
        raise CrawlStopped("DOMAIN_OR_PORT_NOT_ALLOWED")
    if any(ord(c) < 32 for c in url) or "\\" in url:
        raise CrawlStopped("INVALID_URL")
    if re.search(r"%(?:2e|2f|5c|25)", p.path, re.I) or any(part in {".", ".."} for part in p.path.split("/")):
        raise CrawlStopped("AMBIGUOUS_PATH")
    from app.services.url_safety import assert_no_credentials
    try:assert_no_credentials(url)
    except ValueError as exc:raise CrawlStopped(str(exc)) from None
    return host, port


def public_addresses(host: str, port: int) -> frozenset[str]:
    try:
        addresses = frozenset(r[4][0] for r in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
    except OSError:
        raise CrawlStopped("DNS_FAILED") from None
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise CrawlStopped("NON_PUBLIC_DNS")
    return addresses


@dataclass
class Response:
    original_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    headers: dict

    def text(self) -> str:
        charset = re.search(r"charset=([\w-]+)", self.content_type, re.I)
        try:
            return self.body.decode(charset.group(1) if charset else "utf-8", errors="replace")
        except LookupError:
            raise CrawlStopped("UNKNOWN_ENCODING") from None


class SafeFetch:
    """每跳同源许可+robots；DNS 重检后连固定 IP，TLS SNI/证书仍校验域名。"""
    def __init__(self, domains: set[str], *, timeout=10, max_bytes=2_000_000,
                 total_bytes=8_000_000, interval=2.0, max_requests=30, allowed_paths=None):
        self.domains = domains
        self.allowed_paths = tuple(allowed_paths or ["/"])
        self.timeout = min(float(timeout), 15)
        self.max_bytes = min(int(max_bytes), 2_000_000)
        self.total_bytes = min(int(total_bytes), 8_000_000)
        self.interval = max(float(interval), 2.0)
        self.max_requests = min(int(max_requests), 30)
        self.pins: dict[str, frozenset[str]] = {}
        self.robots: dict[str, RobotFileParser] = {}
        self.bytes = 0
        self.requests = 0
        self.started = time.monotonic()
        self.request_lock = threading.RLock()

    def _one(self, url: str) -> Response:
        with _HTTP_SLOT:
            return self._one_locked(url)

    def _one_locked(self, url: str) -> Response:
        host, port = check_url(url, self.domains)
        if time.monotonic() - self.started > 60 or self.requests >= self.max_requests:
            raise CrawlStopped("FETCH_RESOURCE_LIMIT")
        addresses = public_addresses(host, port)
        if host in self.pins and addresses != self.pins[host]:
            raise CrawlStopped("DNS_CHANGED")
        self.pins[host] = addresses
        with _LOCK:
            wait = self.interval - (time.monotonic() - _LAST.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            _LAST[host] = time.monotonic()
        self.requests += 1
        if time.monotonic() - self.started > 60 or self.requests > self.max_requests:
            raise CrawlStopped("FETCH_RESOURCE_LIMIT")
        sock = None
        conn = http.client.HTTPConnection(host, port, timeout=self.timeout)
        try:
            # 不再次解析域名：socket.create_connection 的 host 为已验证的数字 IP。
            sock = socket.create_connection((sorted(addresses)[0], port), timeout=self.timeout)
            if sock.getpeername()[0] not in addresses:
                raise CrawlStopped("PEER_IP_MISMATCH")
            if urlsplit(url).scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            conn.sock = sock
            p = urlsplit(url)
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            conn.request("GET", path, headers={"Host": host, "User-Agent": USER_AGENT,
                         "Accept-Encoding": "identity", "Connection": "close"})
            res = conn.getresponse()
            headers = {k.lower(): v for k, v in res.getheaders()}
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise CrawlStopped("ENCODED_BODY_NOT_ALLOWED")
            size = headers.get("content-length")
            if size and (not size.isdigit() or int(size) > self.max_bytes):
                raise CrawlStopped("BODY_SIZE_LIMIT")
            parts = []
            size_read = 0
            while chunk := res.read(65536):
                size_read += len(chunk)
                self.bytes += len(chunk)
                if size_read > self.max_bytes or self.bytes > self.total_bytes or time.monotonic() - self.started > 60:
                    raise CrawlStopped("BODY_RESOURCE_LIMIT")
                parts.append(chunk)
            if res.status in {401, 403, 429}:
                raise CrawlStopped("ACCESS_DENIED_STOP")
            return Response(url, url, res.status, headers.get("content-type", ""), b"".join(parts), headers)
        except CrawlStopped:
            raise
        except Exception:
            raise CrawlStopped("NETWORK_FAILURE") from None
        finally:
            conn.close()
            if sock:
                sock.close()

    def robot(self, url: str) -> RobotFileParser:
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            # robots 重定向不自动跟随：避免许可尚未建立前跨站。
            result = self._one(origin + "/robots.txt")
            parser = RobotFileParser()
            if result.status in {404, 410}:
                parser.parse(["User-agent: *", "Allow: /"])
            elif result.status == 200:
                parser.parse(result.text().splitlines())
            else:
                raise CrawlStopped("ROBOTS_UNVERIFIED")
            self.robots[origin] = parser
        return self.robots[origin]

    def get(self, url: str) -> Response:
        with self.request_lock:
            return self._get_locked(url)

    def _get_locked(self, url: str) -> Response:
        original = url
        for _ in range(6):
            check_url(url, self.domains)
            path = urlsplit(url).path or "/"
            if not path.startswith(self.allowed_paths) or any(path.lower().startswith(p) for p in (
                "/login", "/signin", "/account", "/admin", "/captcha", "/paywall")):
                raise CrawlStopped("PATH_PERMISSION_DENIED")
            robot = self.robot(url)
            if not robot.can_fetch(USER_AGENT, url):
                raise CrawlStopped("ROBOTS_DENIED")
            delay = robot.crawl_delay(USER_AGENT) or robot.crawl_delay("*")
            rate = robot.request_rate(USER_AGENT) or robot.request_rate("*")
            self.interval = max(self.interval, float(delay or 0), rate.seconds / rate.requests if rate else 0)
            result = self._one(url)
            if result.status in {301, 302, 303, 307, 308}:
                url = urljoin(url, result.headers.get("location", ""))
                check_url(url, self.domains)
                continue
            result.original_url = original
            return result
        raise CrawlStopped("REDIRECT_LIMIT")


def digest(text: str | bytes) -> str:
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()
