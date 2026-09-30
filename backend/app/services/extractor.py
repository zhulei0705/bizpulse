"""手动 URL 分析的底层能力：安全抓取、正文解析、企业识别、规则信号提取。

安全红线（SSRF）：
- 只允许 http/https；
- 拒绝 localhost、内网/链路本地/保留网段 IP（含 DNS 解析结果）；
- 限制超时、重定向次数、内容大小；自定义 UA；不绕过任何登录/验证码/访问控制。
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

_SAFE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::/128"),
]


class URLSafetyError(ValueError):
    """URL 不合法或指向内网资源。"""


def validate_public_url(url: str) -> str:
    """校验并规范化 URL，返回可直接抓取的地址。失败抛 URLSafetyError。"""
    raw = (url or "").strip()
    if not raw:
        raise URLSafetyError("URL 不能为空")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise URLSafetyError("只允许 http/https 协议")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise URLSafetyError("URL 缺少主机名")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        raise URLSafetyError("禁止采集本机或内网主机")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr is not None:
        _ensure_public_ip(addr)
    else:
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", host):
            raise URLSafetyError("主机名不是可解析的公网域名")
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError as exc:
            raise URLSafetyError(f"域名无法解析：{host}") from exc
        for info in infos:
            _ensure_public_ip(ipaddress.ip_address(info[4][0]))
    return raw


def _ensure_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if any(addr in network for network in _SAFE_NETWORKS):
        raise URLSafetyError("禁止采集内网或保留地址")
    if not addr.is_global:
        raise URLSafetyError("禁止采集非公网地址")


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status_code: int
    content_type: str | None
    title: str | None
    text: str
    html: str
    og_site_name: str | None = None
    organization: str | None = None
    meta_description: str | None = None
    published_at_raw: str | None = None
    matches: dict = field(default_factory=dict)


class FetchedItemAdapter(FetchedPage):
    """把 CollectorAdapter 的 CollectedItem 适配为 FetchedPage 形态，
    复用企业识别与规则信号提取（不复制逻辑、不引入第二套解析）。"""

    def __init__(self, item) -> None:  # item: app.collectors.base.CollectedItem
        super().__init__(
            url=item.url,
            final_url=item.url,
            status_code=item.http_status or 0,
            content_type=item.content_type,
            title=item.title,
            text=item.raw_text or "",
            html="",
            og_site_name=item.extra.get("og_site_name"),
            organization=item.extra.get("organization"),
            meta_description=item.extra.get("meta_description"),
        )


def fetch_public_page(url: str) -> FetchedPage:
    """抓取公开网页。大小/超时/重定向均受 settings 限制。"""
    safe_url = validate_public_url(url)
    headers = {
        "User-Agent": settings.ingest_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    with httpx.Client(
        timeout=settings.ingest_timeout_seconds,
        follow_redirects=True,
        max_redirects=settings.ingest_max_redirects,
        headers=headers,
    ) as client:
        with client.stream("GET", safe_url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if content_type and not content_type.lower().startswith(("text/html", "application/xhtml", "text/plain")):
                raise URLSafetyError(f"不支持的网页内容类型：{content_type.split(';')[0].strip()}")
            declared = response.headers.get("content-length")
            if declared and int(declared) > settings.ingest_max_bytes:
                raise URLSafetyError("网页内容超过大小限制")
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > settings.ingest_max_bytes:
                    raise URLSafetyError("网页内容超过大小限制")
                chunks.append(chunk)
            html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    return parse_html(safe_url, str(response.url), response.status_code, content_type, html)


_DROP_TAGS = ("script", "style", "noscript", "svg", "iframe", "nav", "footer", "aside", "form", "template")


def parse_html(url: str, final_url: str, status_code: int, content_type: str | None, html: str) -> FetchedPage:
    soup = BeautifulSoup(html, "html.parser")

    og_site_name = _meta(soup, "og:site_name")
    meta_description = _meta(soup, "description")
    published_at_raw = _detect_publish_time(soup)

    organization = _jsonld_organization(soup)

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    title = re.sub(r"\s+", " ", title or "").strip() or None

    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()
    main = soup.body or soup
    text = re.sub(r"[ \t\r\f]+", " ", main.get_text(" ", strip=True))
    text = re.sub(r"\n{2,}", "\n", text).strip()

    return FetchedPage(
        url=url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        title=title,
        text=text[: settings.ingest_max_text_chars],
        html=html[: settings.ingest_max_bytes],
        og_site_name=og_site_name,
        organization=organization,
        meta_description=meta_description,
        published_at_raw=published_at_raw,
    )


def _meta(soup: BeautifulSoup, key: str) -> str | None:
    if key.startswith("og:"):
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    else:
        tag = soup.find("meta", attrs={"name": key})
    if not tag:
        return None
    value = (tag.get("content") or "").strip()
    return value or None


def _jsonld_organization(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                candidates.extend(g for g in graph if isinstance(g, dict))
            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(t in ("Organization", "Corporation", "LocalBusiness") for t in types if isinstance(t, str)):
                name = item.get("name") or item.get("legalName")
                if name and isinstance(name, str):
                    return name.strip()
    return None


_TIME_PATTERNS = (
    r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)",
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)",
)


def _detect_publish_time(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all(("time", "meta")):
        value = tag.get("datetime") or tag.get("content") or tag.get_text(" ", strip=True)
        if value:
            return value.strip()[:64]
    return None


def content_fingerprint(url: str, title: str | None, text: str) -> str:
    return hashlib.sha256(f"{url}\n{title or ''}\n{text}".encode("utf-8")).hexdigest()


def domain_of(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host or None


def site_origin(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


# ---------------------------------------------------------------------------
# 企业识别（规则优先，识别不了返回 None，绝不猜测）
# ---------------------------------------------------------------------------

_TITLE_SPLITTERS = re.compile(r"\s*[|｜\-–—_·•]\s*|\s*[–—]\s*")


def identify_company(page: FetchedPage) -> str | None:
    """按优先级识别企业名：JSON-LD Organization > og:site_name > 域名。识别不了返回 None。"""
    if page.organization and _plausible_name(page.organization):
        return page.organization
    if page.og_site_name and _plausible_name(page.og_site_name):
        return page.og_site_name
    host = domain_of(page.final_url)
    if host:
        core = host.removeprefix("www.").split(".")[0]
        if core and not core.isdigit() and core not in {"com", "cn", "www"}:
            return core
    if page.title:
        candidate = _TITLE_SPLITTERS.split(page.title)[0].strip()
        if _plausible_name(candidate) and len(candidate) <= 40:
            return candidate
    return None


def _plausible_name(name: str | None) -> bool:
    if not name:
        return False
    cleaned = name.strip()
    if not (1 < len(cleaned) <= 60):
        return False
    if re.search(r"(订阅|登录|注册|cookie|javascript|404|not found)", cleaned, re.I):
        return False
    return True


# ---------------------------------------------------------------------------
# 规则 Signal 提取（Rule Engine）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleHit:
    signal_type: str
    title: str
    excerpt: str
    confidence: int


class _Rule:
    def __init__(self, signal_type: str, label: str, patterns: list[str], confidence: int) -> None:
        self.signal_type = signal_type
        self.label = label
        self.regex = re.compile("|".join(patterns), re.I)
        self.confidence = confidence


_RULES: list[_Rule] = [
    _Rule("SALES_HIRING", "销售团队招聘", [r"招聘.{0,12}(海外销售|销售(经理|总监|工程师|代表)?|大客户经理|商务拓展|BD)", r"(海外销售|销售总监|销售经理|大客户经理|BD经理).{0,6}(招聘|急聘|热招)"], 78),
    _Rule("AI_HIRING", "AI人才招聘", [r"招聘.{0,10}(AI|人工智能|算法|大模型|机器学习|LLM|NLP)", r"(算法工程师|大模型工程师|AI工程师|机器学习工程师).{0,6}(招聘|急聘|热招)"], 80),
    _Rule("CUSTOMER_SERVICE_HIRING", "客服团队招聘", [r"招聘.{0,10}(客服|客户服务|客户成功|售后)", r"(客服专员|客户成功经理|售后服务).{0,6}(招聘|急聘)"], 72),
    _Rule("FINANCE_HIRING", "财务人员招聘", [r"招聘.{0,10}(财务|会计|审计|税务)", r"(财务经理|会计|审计员|税务专员).{0,6}(招聘|急聘)"], 70),
    _Rule("HIRING", "招聘扩张", [r"(诚聘|急聘|热招|加入我们|join\s+us|we.?re\s+hiring|人才招聘|校园招聘|社会招聘)", r"招聘\d+名"], 62),
    _Rule("FUNDING", "融资事件", [r"完成.{0,10}(天使轮|Pre-[A-Z轮]|A\+?轮|B\+?轮|C\+?轮|战略融资|股权融资)", r"(获得|宣布).{0,12}(融资|投资)", r"(亿元|万美元|千万).{0,4}(融资|投资)"], 85),
    _Rule("OVERSEAS_EXPANSION", "海外扩张", [r"(出海|海外(市场|业务|扩张|布局|分公司|办事处)|进军国际|全球化战略|设立海外)", r"( opens? | launches? ).{0,20}(office|subsidiary).{0,20}(overseas|international)"], 75),
    _Rule("EXPANSION", "业务扩张", [r"(新(建|设|开)(工厂|基地|产线|分公司|办事处|中心)|扩(建|大)产能|产能扩张|规模扩大|增资扩产)"], 70),
    _Rule("NEW_PRODUCT", "新产品发布", [r"(发布(全新|新一代|最新)?(产品|版本|平台|系统|服务)|新品上市|product launch|全新上线)", r"(正式推出|重磅推出|首发)"], 74),
    _Rule("NEW_MARKET", "新市场进入", [r"(进军|切入|布局).{0,12}(市场|领域|行业)", r"新市场.{0,6}(开拓|拓展|进入)"], 66),
    _Rule("TENDER", "招标信息", [r"(招标|询价公告|竞标公告|采购公告|招投标)", r"(招标编号|采购项目编号)"], 82),
    _Rule("PROCUREMENT", "采购需求", [r"(采购(需求|计划|清单|公告)?[,，]?\s*(数量|金额|预算)?)", r"公开采购"], 74),
    _Rule("CRM_DEMAND", "CRM需求", [r"((客户管理|CRM|销售管理).{0,14}(系统|软件|平台|工具).{0,10}(需求|招标|采购|选型)?)", r"(CRM系统|客户管理系统)"], 60),
    _Rule("ERP_DEMAND", "ERP需求", [r"((ERP|进销存|供应链管理|生产管理).{0,10}(系统|软件|平台).{0,10}(需求|招标|采购|选型)?)", r"(ERP系统|进销存系统)"], 60),
    _Rule("CUSTOMER_COMPLAINT", "客户投诉", [r"(客户(投诉|抱怨|不满)|投诉量|售后投诉|集中投诉)"], 68),
    _Rule("COST_PRESSURE", "成本压力", [r"(成本(上涨|上升|压力|管控|控制|下降难)|原材料涨价|人力成本|降本增效|利润下滑)"], 70),
    _Rule("EFFICIENCY_PROBLEM", "效率问题", [r"(效率(低|低下|不高)|人工(处理|登记|录入|对账|排班)|重复劳动|手工操作|耗时.{0,6}小时)"], 68),
    _Rule("DIGITAL_TRANSFORMATION", "数字化转型", [r"(数字化(转型|升级|改造)|信息化建设|智能(化升级|制造)|上云)"], 72),
    _Rule("AI_TRANSFORMATION", "AI转型", [r"(AI(赋能|转型|落地|升级)|人工智能(应用|落地|转型)|智能化转型|大模型(应用|落地))"], 76),
    _Rule("MANUAL_WORK", "人工操作痛点", [r"(人工(审核|录入|填写|统计|核对|报表)|纯手工|手动(录入|登记|统计))"], 66),
    _Rule("DATA_PROBLEM", "数据问题", [r"(数据(孤岛|分散|不一致|缺失|混乱)|信息(孤岛|不透明)|数据无法(打通|互通))"], 66),
]

_EXCERPT_WINDOW = 60


def extract_signal_hits(page: FetchedPage) -> list[RuleHit]:
    """规则引擎：从标题+正文识别真实发生的商业事件关键词。全部为“事实”级命中。"""
    haystack = f"{page.title or ''}\n{page.meta_description or ''}\n{page.text[:60000]}"
    hits: list[RuleHit] = []
    seen_types: set[str] = set()
    for rule in _RULES:
        match = rule.regex.search(haystack)
        if not match:
            continue
        start = max(0, match.start() - _EXCERPT_WINDOW)
        end = min(len(haystack), match.end() + _EXCERPT_WINDOW)
        excerpt = re.sub(r"\s+", " ", haystack[start:end]).strip()
        confidence = rule.confidence if match.group(0).count("\n") == 0 else max(50, rule.confidence - 15)
        hits.append(RuleHit(
            signal_type=rule.signal_type,
            title=f"{rule.label}",
            excerpt=excerpt,
            confidence=confidence if page.title and rule.regex.search(page.title or "") else max(55, confidence - 10),
        ))
        seen_types.add(rule.signal_type)
    # 去掉被更具体类型覆盖的泛化信号（例如同时命中 HIRING 与 SALES_HIRING）
    specific = {"SALES_HIRING", "AI_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING"}
    if specific & seen_types:
        hits = [h for h in hits if h.signal_type != "HIRING"]
    return hits[:8]
