"""T08 企业发现与官网站内发现（WebsiteDiscovery）。

原则（任务书五~八、五十三）：
- 只抓公开页面；限速；限同域名；不整站爬取（每企业 10~30 个高价值页面）；
- 尊重 robots/网站政策，403 记录并停止，不绕过；
- 所有发现必须保存真实来源 URL（可追溯：Company → Discovery Source → SourceRecord）。
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import COMPANY_VERIFICATION_STATUSES
from app.models.company import Company
from app.services import extractor
from app.services.extractor import FetchedPage, URLSafetyError

logger = logging.getLogger(__name__)

# 站内高价值页面分类（关键词 → 维度）
SECTION_PATTERNS: dict[str, re.Pattern] = {
    "NEWS": re.compile(r"(news|xinwen|zx-xw|zx/xw|list.*news|xwzx|newscenter|press|media|新闻|动态|资讯|公司动态|新闻中心|媒体报道)", re.I),
    "CAREERS": re.compile(r"(career|jobs|job|recruit|hire|zhaopin|zp|rencai|join[_-]?us|招聘|人才|加入我们|人才招聘|诚聘|英才|招贤|求职)", re.I),
    "CONTACT": re.compile(r"(contact|lianxi|lxwm|lxfs|contactus|联系我们|联系方式|联系)", re.I),
    "PRODUCTS": re.compile(r"(product|chanpin|cpzx|productlist|products|产品|产品中心|产品与服务)", re.I),
    "SOLUTIONS": re.compile(r"(solution|fangan|jiejuefangan|services|服务|解决方案|行业方案)", re.I),
    "ABOUT": re.compile(r"(about|guanyu|gywm|jianjie|概况|关于|简介|关于我们|公司简介)", re.I),
}

MAX_DISCOVERY_PAGES = 30  # 单企业官网发现上限（任务书七：10~30 页）
FETCH_DELAY_SECONDS = 1.2  # 限速

# T08.2 页面类型（任务书九）
PAGE_TYPES = (
    "HOME", "NEWS_INDEX", "NEWS_ARTICLE", "CAREERS", "JOB_DETAIL",
    "PRODUCT", "SOLUTION", "CONTACT", "ABOUT", "OTHER",
)

_NEWS_ARTICLE_HINT = re.compile(r"(/\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8,14}|detail|article|view|info/|news/)", re.I)
_JOB_DETAIL_HINT = re.compile(r"(job|position|zhiwei|gongwei|岗位|职位|职位详情)", re.I)


def classify_page_type(url: str, title: str | None = None, text: str | None = None) -> str:
    """按 URL + 标题判断页面类型（任务书九；不同类型用不同解析逻辑）。"""
    combined = f"{url} {title or ''}"
    for dimension in ("CONTACT", "CAREERS", "PRODUCTS", "SOLUTIONS", "ABOUT", "NEWS"):
        if SECTION_PATTERNS[dimension].search(combined):
            if dimension == "NEWS":
                # 文章页：URL 含 detail/article/view 或深日期路径；标题带栏目词的列表页归 INDEX
                looks_article = bool(re.search(r"(detail|article|view|info/)", url, re.I))
                dated_path = bool(re.search(r"/\d{4}/\d{1,2}/\d{1,2}/", url))
                title_is_index = bool(SECTION_PATTERNS["NEWS"].search(title or ""))
                if (looks_article or dated_path) and not title_is_index:
                    return "NEWS_ARTICLE"
                return "NEWS_INDEX"
            if dimension == "CAREERS" and _JOB_DETAIL_HINT.search(url):
                return "JOB_DETAIL"
            return {
                "NEWS": "NEWS_INDEX", "CAREERS": "CAREERS", "CONTACT": "CONTACT",
                "PRODUCTS": "PRODUCT", "SOLUTIONS": "SOLUTION", "ABOUT": "ABOUT",
            }[dimension]
    # 正文含大量岗位条目的列表页归 CAREERS
    if text and len(re.findall(r"(招聘|岗位|职位)[^\n]{0,40}", text[:4000])) >= 3:
        return "CAREERS"
    return "OTHER"

# 中标供应商提取（真实公告常见写法；只取"中标/成交"，不取候选/采购人）
_SUPPLIER_PATTERNS = [
    re.compile(r"中标(?:供应商|人|单位)名称[：:]\s*([^\s，,。；;]{4,80})"),
    re.compile(r"中标(?:供应商|人|单位)[：:]\s*([^\s，,。；;]{4,80})"),
    re.compile(r"成交供应商名称[：:]\s*([^\s，,。；;]{4,80})"),
    re.compile(r"成交(?:供应商|人)[：:]\s*([^\s，,。；;]{4,80})"),
    re.compile(r"供应商名称[：:]\s*([^\s，,。；;]{4,80})"),
]
_COMPANY_SUFFIX = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9（）()·]+(?:股份有限公司|有限责任公司|有限公司|集团|公司)$")
# 采购主体（不是供应商）：不得当作中标企业入库
_BUYER_HINTS = ("采购人", "采购单位", "招标人", "采购单位名称")


@dataclass
class DiscoveredSection:
    """官网站内发现的一个高价值页面。"""

    dimension: str  # NEWS/CAREERS/CONTACT/PRODUCTS/SOLUTIONS/ABOUT
    url: str
    title: str | None = None


@dataclass
class WebsiteDiscoveryResult:
    official_url: str
    pages: list[DiscoveredSection] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def classify_link(url: str, text: str) -> str | None:
    """按 URL/锚文本判断站内页面维度（只认高价值栏目，避免无意义爬取）。"""
    combined = f"{url} {text}"
    for dimension, pattern in SECTION_PATTERNS.items():
        if pattern.search(combined):
            return dimension
    return None


def discover_website_sections(official_url: str, *, max_pages: int = MAX_DISCOVERY_PAGES) -> WebsiteDiscoveryResult:
    """抓企业官网首页，发现同域名下的新闻/招聘/联系/产品等高价值页面。

    限制：仅同域名；每个维度最多 2 个候选页；总量 ≤ max_pages；单页失败记录不中断。
    """
    result = WebsiteDiscoveryResult(official_url=official_url)
    try:
        home = extractor.fetch_public_page(official_url)
    except (URLSafetyError, RuntimeError) as exc:
        result.errors.append(f"homepage_fetch_failed: {str(exc)[:150]}")
        return result

    host = urlparse(home.final_url).netloc
    seen_urls = {home.final_url}
    per_dimension: dict[str, int] = {}

    def _add(dimension: str, url: str, title: str | None) -> bool:
        if len(result.pages) >= max_pages:
            return False
        if per_dimension.get(dimension, 0) >= 2:
            return False
        result.pages.append(DiscoveredSection(dimension=dimension, url=url, title=title))
        per_dimension[dimension] = per_dimension.get(dimension, 0) + 1
        return True

    # 首页本身按 ABOUT 记录
    _add("ABOUT", home.final_url, home.title)

    soup = extractor.parse_soup(home.html) if hasattr(extractor, "parse_soup") else None
    if soup is None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(home.html, "html.parser")

    for anchor in soup.find_all("a", href=True):
        if len(result.pages) >= max_pages:
            break
        raw_href = anchor["href"].strip()
        if not raw_href or raw_href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = urljoin(home.final_url, raw_href)
        parsed = urlparse(absolute)
        if parsed.netloc != host:  # 限同域名
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        dimension = classify_link(normalized, anchor.get_text(" ", strip=True)[:60])
        if dimension:
            _add(dimension, normalized, anchor.get_text(" ", strip=True)[:120] or None)

    return result


def extract_awarded_suppliers(text: str | None) -> list[dict]:
    """从真实中标/成交公告正文提取中标供应商（只取中标，不取候选人与采购人）。

    返回 [{name, matched_pattern}]；名称用"有限公司/集团"后缀正则再校验，提取不到
    完整公司名时保留原始片段（后续人工确认），绝不猜测。
    """
    if not text:
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for pattern in _SUPPLIER_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1).strip()
            if not raw or raw in seen:
                continue
            # 清洗：截掉后面粘连的其他字段
            cleaned = re.split(r"(?:项目名称|采购人|中标金额|地址|电话)", raw)[0].strip("：: ，,。；;")
            if not cleaned:
                continue
            seen.add(raw)
            suffix_match = _COMPANY_SUFFIX.search(cleaned)
            name = suffix_match.group(0) if suffix_match else cleaned
            found.append({"name": name, "raw": raw, "matched": pattern.pattern[:30]})
    return found


def upsert_discovered_company(
    db: Session,
    *,
    name: str,
    source_url: str,
    source_title: str | None = None,
    organization_type: str = "UNKNOWN",
    domain: str | None = None,
) -> tuple[Company, bool]:
    """把从真实公开来源发现的企业入正式库（Company Gate，任务书十九/二十）。

    - 来源必须存在（source_url），否则拒绝；
    - 去重优先 domain，其次 normalized_name（复用 CompanyResolver 规则），禁止仅相似名称合并；
    - 来源为可信官方公开公告 → PUBLIC_SOURCE_VERIFIED（不是 WEBSITE_VERIFIED，官网需另行验证）。
    """
    if not source_url:
        raise ValueError("发现来源 URL 必须存在（可追溯要求）")
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("企业名称必须存在")
    if organization_type not in COMPANY_VERIFICATION_STATUSES and organization_type not in {
        "COMPANY", "GOVERNMENT", "UNIVERSITY", "RESEARCH_INSTITUTE", "HOSPITAL", "NON_PROFIT", "ASSOCIATION", "OTHER", "UNKNOWN",
    }:
        raise ValueError(f"未知组织类型：{organization_type}")

    # 去重：domain 优先 → normalized_name
    company: Company | None = None
    if domain:
        company = db.scalar(select(Company).where(Company.domain == domain.lower()))
    if company is None:
        normalized = "".join(clean_name.lower().split())
        company = db.scalar(select(Company).where(Company.normalized_name == normalized))
    if company is not None:
        return company, False  # 已存在（重复发现，不新建）

    company = Company(
        company_name=clean_name[:300],
        normalized_name="".join(clean_name.lower().split())[:300] or clean_name.lower()[:300],
        domain=domain,
        organization_type=organization_type,
        verification_status="PUBLIC_SOURCE_VERIFIED",
        discovery_source_url=source_url,
        verified_at=datetime.now(timezone.utc),
        source_count=0,
    )
    db.add(company)
    db.flush()
    return company, True
