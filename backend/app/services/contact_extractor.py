"""T08.2 联系渠道抽取器：只认网页原文直接公开的联系方式（任务书十五~十九）。

红线：
- NO_GUESSED_EMAIL_AS_VERIFIED：禁止 姓名+域名 推断邮箱；邮箱必须原文存在才入库；
- 只有网页直接公开的联系方式才可标 VERIFIED_PUBLIC；
- HR/客服/媒体等渠道仅证明"可触达"，is_decision_maker 一律 False（不得无依据升级）；
- 无邮箱但有官方联系表单 → WEBSITE_FORM 渠道（与 EMAIL/PHONE 明确区分）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.core.constants import is_source_platform_domain

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:1[3-9]\d{9}|400[-\s]?\d{3}[-\s]?\d{4}|0\d{2,3}[-\s]?\d{7,8})")

# 联系人角色（按邮箱账号前缀 / 上下文标签判定，规则可解释）
_ROLE_PREFIX_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"^(sales?|sale|xiaoshou)", re.I), "SALES"),
    (re.compile(r"^(hr|job|jobs|career|careers|zhaopin|recruit|renshi|hrbp)", re.I), "HR"),
    (re.compile(r"^(bd|business|coop|cooperation|hezu|partner|partnership)", re.I), "BUSINESS"),
    (re.compile(r"^(press|media|pr@|marketing)", re.I), "PRESS"),
    (re.compile(r"^(buy|purchas|caigou|procurement|sourcing)", re.I), "PROCUREMENT"),
    (re.compile(r"^(service|support|kf|kefu|cs)", re.I), "CUSTOMER_SERVICE"),
    (re.compile(r"^(ceo|cto|cfo|coo|president|gm)", re.I), "EXECUTIVE"),
    (re.compile(r"^(project|pmo|xiangmu)", re.I), "PROJECT"),
    (re.compile(r"^(agent|daili|channel|qudao)", re.I), "PARTNERSHIP"),
    (re.compile(r"^(info|contact|office|hello|mail|email)", re.I), "GENERAL"),
)
# 上下文角色标签（邮箱/电话前的文字）
_ROLE_CONTEXT_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(销售|市场)[^，,。；;\n]{0,6}(邮箱|电话|热线|联系)", re.I), "SALES"),
    (re.compile(r"(招聘|人才|人力|HR)[^，,。；;\n]{0,6}(邮箱|电话|联系)", re.I), "HR"),
    (re.compile(r"(商务|合作|渠道|招商)[^，,。；;\n]{0,6}(邮箱|电话|联系)", re.I), "BUSINESS"),
    (re.compile(r"(媒体|采访|公关)[^，,。；;\n]{0,6}(邮箱|电话|联系)", re.I), "PRESS"),
    (re.compile(r"(采购)[^，,。；;\n]{0,6}(邮箱|电话|联系)", re.I), "PROCUREMENT"),
    (re.compile(r"(客服|售后|支持)[^，,。；;\n]{0,6}(邮箱|电话|热线)", re.I), "CUSTOMER_SERVICE"),
    (re.compile(r"(项目)[^，,。；;\n]{0,6}(邮箱|电话|联系)", re.I), "PROJECT"),
)
_DEFAULT_ROLE = "GENERAL"

# 联系表单页特征（无邮箱/电话时的可触达渠道）
_FORM_KEYWORDS = re.compile(r"(在线留言|留言板|联系表单|在线咨询|在线反馈|message|feedback|enquiry|inquiry|get[-_ ]?in[-_ ]?touch|contact[-_ ]?us|联系我们)", re.I)
_FORM_ACTION_HINT = re.compile(r"<form[^>]+action=", re.I)

# 明显非企业主体的公共邮箱白名单（真实存在即可保留，但仍是公开渠道而非个人）
_KNOWN_PERSONAL_DOMAINS = ("qq.com", "163.com", "126.com", "sina.com", "gmail.com", "outlook.com", "hotmail.com", "foxmail.com")


@dataclass
class ContactDraft:
    """抽取出的联系渠道草稿（未入库；入库前需确认来源页面归属）。"""

    channel: str  # EMAIL / PHONE / WEBSITE_FORM
    contact_type: str  # CONTACT_BUSINESS_TYPES 取值
    email: str | None = None
    phone: str | None = None
    form_url: str | None = None
    name: str | None = None
    title: str | None = None
    department: str | None = None
    evidence_text: str | None = None


def _role_from_prefix(email: str) -> str | None:
    local = email.split("@", 1)[0]
    for pattern, role in _ROLE_PREFIX_RULES:
        if pattern.match(local):
            return role
    return None


def _role_from_context(text: str, pos: int) -> str | None:
    window = text[max(0, pos - 60):pos]
    for pattern, role in _ROLE_CONTEXT_RULES:
        if pattern.search(window):
            return role
    return None


def _clean_name(raw: str | None) -> str | None:
    if not raw:
        return None
    name = raw.strip()
    if not name or len(name) > 20:
        return None
    return name


def _is_third_party_tracker(email: str, company_domain: str | None) -> bool:
    """排除明显非企业联系用途的邮箱（第三方服务/示例域）。"""
    domain = email.split("@", 1)[1].lower()
    if company_domain:
        base = company_domain.lower()
        for prefix in ("www.", "mail.", "smtp."):
            if base.startswith(prefix):
                base = base[len(prefix):]
        if domain == base or domain.endswith(f".{base}"):
            return False  # 本企业域名下的邮箱
    if domain in _KNOWN_PERSONAL_DOMAINS:
        return False  # 公共邮箱域（163/QQ等）在官网明示时仍为真实公开渠道，保留但按规则归类
    if any(bad in domain for bad in ("example.", "sentry", "wixpress", "wix.com", "squarespace", "cdn.", "cloudflare")):
        return True
    if is_source_platform_domain(domain):
        return True
    return False


def extract_contacts(text: str | None, *, page_url: str, company_domain: str | None = None,
                     page_is_contact: bool = False) -> list[ContactDraft]:
    """从官网页面原文抽取公开联系渠道（邮箱/电话/表单）。原文没有就不产出。"""
    if not text:
        return []
    body = text[:60_000]
    drafts: list[ContactDraft] = []
    seen: set[tuple] = set()

    # 1) 邮箱（原文必须存在）
    for m in _EMAIL_PATTERN.finditer(body):
        email = m.group(0).strip().strip(".").lower()
        if _is_third_party_tracker(email, company_domain):
            continue
        role = _role_from_prefix(email) or _role_from_context(body, m.start()) or _DEFAULT_ROLE
        key = ("EMAIL", email)
        if key in seen:
            continue
        seen.add(key)
        evidence = body[max(0, m.start() - 30):m.end() + 30].strip()
        name = None
        name_match = re.search(r"联\s*系\s*人[：:]\s*([^\s，,。；;@]{2,10})", body[max(0, m.start() - 120):m.start()])
        if name_match:
            name = _clean_name(name_match.group(1))
        drafts.append(ContactDraft(channel="EMAIL", contact_type=role, email=email,
                                   name=name, evidence_text=evidence))

    # 2) 电话（原文必须存在；带角色标签时归类）
    for m in _PHONE_PATTERN.finditer(body):
        phone = re.sub(r"\s+", "", m.group(0))
        role = _role_from_context(body, m.start()) or _DEFAULT_ROLE
        key = ("PHONE", phone, role)
        if any(k[1] == phone for k in seen):
            continue
        seen.add(key)
        evidence = body[max(0, m.start() - 30):m.end() + 30].strip()
        drafts.append(ContactDraft(channel="PHONE", contact_type=role, phone=phone, evidence_text=evidence))

    # 3) 联系表单渠道：联系页出现表单特征/关键词（无邮箱电话时尤其重要）
    has_form = page_is_contact and bool(_FORM_KEYWORDS.search(f"{body[:3000]}"))
    if has_form and not any(d.channel == "EMAIL" for d in drafts):
        drafts.append(ContactDraft(channel="WEBSITE_FORM", contact_type="GENERAL",
                                   form_url=page_url,
                                   evidence_text=_FORM_KEYWORDS.search(body[:3000]).group(0)))
    return drafts


def contact_channel(verification_status_or_row) -> str | None:
    """由字段推导联系渠道：EMAIL / PHONE / WEBSITE_FORM（不新增列）。
    接受 CompanyContact 行或 (email, phone, public_profile_url) 元组。"""
    if hasattr(verification_status_or_row, "email"):
        email = verification_status_or_row.email
        phone = verification_status_or_row.phone
        form = verification_status_or_row.public_profile_url
    else:
        email, phone, form = verification_status_or_row
    if email:
        return "EMAIL"
    if phone:
        return "PHONE"
    if form:
        return "WEBSITE_FORM"
    return None


def classify_contact_page(url: str, title: str | None) -> bool:
    """该页面是否为联系页（用于 WEBSITE_FORM 判定）。"""
    combined = f"{url} {title or ''}"
    return bool(re.search(r"(contact|lianxi|lxwm|lxfs|联系我们|联系方式|联系)", combined, re.I))


def site_domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    return host
