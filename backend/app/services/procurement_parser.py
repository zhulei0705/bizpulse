"""T08.0 政府采购公告结构化解析器（P0-5 published_at / P0-6 ContactExtractor）。

全部基于真实公告正文的结构化字段（"采购人：""公告时间：""预算金额："等），
解析不到就返回 None/UNKNOWN，绝不猜测。联系人区分采购人/代理机构/项目联系人。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

# 常见角色区分（任务书 P0-6：不能把代理公司联系人错误归属于采购单位）
CONTACT_TYPE_LABELS = {
    "PURCHASER_CONTACT": "采购人联系人",
    "AGENCY_CONTACT": "代理机构联系人",
    "PROJECT_CONTACT": "项目联系人",
}

_AMOUNT_PATTERN = re.compile(
    r"(预算金额|最高限价|采购预算|中标金额|成交金额|合同金额)[^0-9￥¥]{0,6}(￥|¥)?\s*([\d,，]+(?:\.\d+)?)\s*(万?元)?"
)
_DATE_PATTERNS = (
    re.compile(r"(公告时间|发布时间|公告日期|发布日期)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)"),
    re.compile(r"(公告时间|发布时间|公告日期|发布日期)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)"),
)
_DEADLINE_PATTERNS = (
    re.compile(r"((?:提交)?(?:投标|响应)(?:文件)?(?:递交)?)截止时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*\d{1,2}(?:[点时]\d{1,2}分(?:\d{1,2}秒)?|[:：]\d{1,2}(?:[:：]\d{1,2})?))"),
    re.compile(r"(投标|响应|递交|报名)截止时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)"),
    re.compile(r"(投标|响应|递交|报名)截止时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)"),
)
_PROJECT_NAME_PATTERN = re.compile(r"项目名称[：:]\s*([^\s，,。；;]{4,120})")
_PURCHASER_NAME_PATTERN = re.compile(r"采\s*购\s*人[名称]?[：:]\s*([^\s，,。；;（(]{4,80})")
_CATEGORY_PATTERN = re.compile(r"采购品目[：:]\s*([^\s，,。；;]{2,60})")

# T08.0：ccgp 表格压平后的真实格式（无冒号）
# "采购单位 华南理工大学 行政区域 广州市 公告时间 2026年09月30日 19:45"
# "1.采购人信息 名 称：华南理工大学 地址：..."
_TABLE_PURCHASER_PATTERN = re.compile(r"采购单位\s+([^\s，,。；;（(]{4,80})\s+行政区域")
_INFO_PURCHASER_PATTERN = re.compile(r"采\s*购\s*人\s*信\s*息\s*名\s*称[：:]\s*([^\s，,。；;（(]{4,80})")
_TABLE_TIME_PATTERN = re.compile(
    r"公告时间\s+(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)"
)
_TABLE_DEADLINE_PATTERN = re.compile(
    r"(投标|响应|递交|报名)截止时间\s+(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)"
)

_PHONE_PATTERN = re.compile(r"(1[3-9]\d{9}|0\d{2,3}-?\d{7,8}|0\d{2,3}\d{7,8})")
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def parse_date_cn(raw: str | None) -> datetime | None:
    """解析中文公告日期（支持 2026年09月30日 19:46 / 2026-09-30 / 2026/09/30）。"""
    if not raw:
        return None
    raw = raw.strip()
    formats = (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        "%Y年%m月%d日 %H:%M:%S", "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
    )
    normalized = raw.replace("年", "-").replace("月", "-").replace("日", " ").replace("：", ":")
    normalized = re.sub(r"(\d{1,2})[点时](\d{1,2})分(?:(\d{1,2})秒)?", lambda m: f"{m[1]}:{m[2]}" + (f":{m[3]}" if m[3] else ""), normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def parse_announcement_time(text: str | None) -> datetime | None:
    """公告时间（P0-5）：优先正文"公告时间："结构化字段（含 ccgp 表格压平的无冒号格式）。

    T08.1 修复：不得把"招标公告发布日期/开标日期/定标日期"误当公告发布时间
    （真实案例：ccgp 中标公告补充事宜里的"招标公告发布日期：2026年9月2日"）。
    """
    if not text:
        return None
    body = text[:20000]
    # ccgp 表格格式（"公告时间 2026年09月30日 18:03"）最可靠，优先
    match = _TABLE_TIME_PATTERN.search(body)
    if match:
        parsed = parse_date_cn(match.group(1))
        if parsed:
            return parsed
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(body):
            # 前文含"招标公告发布/开标/定标/报名"等前缀的日期不是公告发布时间
            prefix = body[max(0, match.start() - 12):match.start()]
            if re.search(r"(招标公告发布|开标|定标|报名)", prefix):
                continue
            parsed = parse_date_cn(match.group(2))
            if parsed:
                return parsed
    return None


def parse_deadline(text: str | None) -> datetime | None:
    """投标/响应截止时间。"""
    if not text:
        return None
    for pattern in _DEADLINE_PATTERNS:
        match = pattern.search(text[:20000])
        if match:
            return parse_date_cn(match.group(2))
    match = _TABLE_DEADLINE_PATTERN.search(text[:20000])
    if match:
        return parse_date_cn(match.group(2))
    return None


def parse_budget_amount(text: str | None) -> float | None:
    """预算/中标金额（万元统一折算为元）。解析不到返回 None，不猜测。"""
    if not text:
        return None
    match = _AMOUNT_PATTERN.search(text[:20000])
    if not match:
        return None
    try:
        amount = float(match.group(3).replace(",", "").replace("，", ""))
    except ValueError:
        return None
    if match.group(4) and "万" in match.group(4):
        amount *= 10000
    return amount


def parse_purchaser(text: str | None) -> str | None:
    """采购单位：支持"采购人："/"采购人信息 名 称："/"采购单位  XXX 行政区域"三种真实格式。"""
    if not text:
        return None
    body = text[:20000]
    match = _PURCHASER_NAME_PATTERN.search(body)
    if match:
        return match.group(1).strip()
    match = _INFO_PURCHASER_PATTERN.search(body)
    if match:
        return match.group(1).strip()
    match = _TABLE_PURCHASER_PATTERN.search(body)
    if match:
        return match.group(1).strip()
    return None


def parse_project_name(text: str | None) -> str | None:
    match = _PROJECT_NAME_PATTERN.search(text[:20000]) if text else None
    return match.group(1).strip() if match else None


def parse_category(text: str | None) -> str | None:
    match = _CATEGORY_PATTERN.search(text[:20000]) if text else None
    return match.group(1).strip() if match else None


@dataclass
class ContactDraft:
    """从公告正文结构化提取的联系人（不猜测；字段缺失保留 None）。"""

    contact_type: str  # PURCHASER_CONTACT / AGENCY_CONTACT / PROJECT_CONTACT
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    organization_name: str | None = None
    raw_section: str = ""


_SECTION_SPLIT = re.compile(
    r"(采\s*购\s*人(?:\s*信息)?|代理机构(?:\s*信息)?|项目联系人|联\s*系\s*方\s*式|联系方式|"
    r"采购人联系方式|代理机构联系方式|项目联系方式)"
)


def extract_procurement_contacts(text: str | None) -> list[ContactDraft]:
    """从公告正文提取联系人（P0-6）—— 按主体声明锚点切分（正文可能是无换行单行）。

    规则：
    - "采购人：XX"声明之后、"代理机构"声明之前的联系信息 → PURCHASER_CONTACT（归属采购单位）；
    - "代理机构名称：XX"声明之后的联系信息 → AGENCY_CONTACT（归属代理公司）；
    - "项目联系人："前缀 → contact_type 标 PROJECT_CONTACT（组织归属不变）；
    - 无任何主体声明但存在联系信息 → PROJECT_CONTACT（不猜归属）；
    - 不把代理机构联系人归属采购单位。
    """
    if not text:
        return []
    body = re.sub(r"\s+", " ", text[:30000]).strip()
    if not body:
        return []

    purchaser_match = _PURCHASER_NAME_PATTERN.search(body) or _INFO_PURCHASER_PATTERN.search(body)
    agency_match = re.search(r"代理机构名称?[：:]\s*([^\s，,。；;（(]{4,80})", body) or re.search(
        r"代\s*理\s*机\s*构\s*信\s*息\s*名\s*称[：:]\s*([^\s，,。；;（(]{4,80})", body
    )
    # 中标供应商声明是最后一个分区边界（其后联系信息不属于采购主体）
    supplier_match = re.search(r"中标(?:供应商|人|单位)名称?[：:]", body)

    agency_start = agency_match.start() if agency_match else (supplier_match.start() if supplier_match else len(body))
    supplier_start = supplier_match.start() if supplier_match else len(body)

    sections: list[tuple[str, str | None, str]] = []
    if purchaser_match and purchaser_match.start() < agency_start:
        sections.append(("PURCHASER_CONTACT", purchaser_match.group(1).strip(), body[:agency_start]))
    if agency_match and agency_match.start() < supplier_start:
        sections.append(("AGENCY_CONTACT", agency_match.group(1).strip(), body[agency_start:supplier_start]))
    if not sections:
        sections.append(("PROJECT_CONTACT", None, body))

    drafts: list[ContactDraft] = []
    seen: set[tuple] = set()
    for contact_type, org_name, section in sections:
        names = [m.group(1).strip() for m in re.finditer(r"(?:项目|代理)?联\s*系\s*人[：:]?\s*([^\s，,。；;]{2,20}?)(?=\s*(?:\d{3,4}-|1[3-9]|邮箱|电话|电话[：:]|[A-Za-z0-9._%+-]+@|$))", section)]
        phones = [m.group(0) for m in _PHONE_PATTERN.finditer(section)]
        emails = [m.group(0) for m in _EMAIL_PATTERN.finditer(section)]
        has_name_marker = bool(re.search(r"联\s*系\s*人[：:]", section))
        rows = max(len(names), len(phones), len(emails))
        if rows == 0:
            continue
        for i in range(rows):
            name = names[i] if i < len(names) else None
            phone = phones[i] if i < len(phones) else None
            email = emails[i] if i < len(emails) else None
            if not (name or phone or email):
                continue
            prefix = None
            if name:
                marker = re.search(r"((?:项目|代理)?联\s*系\s*人)[：:]", section)
                if marker:
                    prefix = marker.group(1).replace(" ", "")
                else:
                    prefix = "联系人"
            resolved_type = "PROJECT_CONTACT" if prefix == "项目联系人" else contact_type
            key = (resolved_type, name, phone, email)
            if key in seen:
                continue
            seen.add(key)
            drafts.append(ContactDraft(
                contact_type=resolved_type,
                name=name,
                phone=phone,
                email=email,
                organization_name=org_name,
                raw_section=section[:200],
            ))
    return drafts


def parse_procurement_fields(text: str | None) -> dict:
    """政采公告结构化字段一次解析（公告时间/截止/预算/采购人/项目名/品目 + 联系人）。"""
    return {
        "announcement_time": parse_announcement_time(text),
        "deadline": parse_deadline(text),
        "budget_amount": parse_budget_amount(text),
        "purchaser": parse_purchaser(text),
        "project_name": parse_project_name(text),
        "category": parse_category(text),
        "contacts": [c for c in extract_procurement_contacts(text)],
        "is_procurement_notice": bool(text and _PROCUREMENT_CONTEXT_LIKE.search(text[:5000] if text else "")),
    }


_PROCUREMENT_CONTEXT_LIKE = re.compile(r"(招标公告|中标公告|成交公告|采购公告|磋商公告|询价公告|采购项目)", re.I)


# ---------------------------------------------------------------------------
# T08.1：CONTRACT_AWARD 语义审计（主体角色 / 中标供应商+金额 / 采购方式 / 生命周期 / 可行动性）
# 原则：所有字段必须能在原文中找到；解析不到返回 None/UNKNOWN，禁止猜测。
# ---------------------------------------------------------------------------

# 主体角色（Signal payload / structured_json 内记录；避免无必要 Migration）
SUBJECT_ROLES = ("BUYER", "SUPPLIER", "PROCUREMENT_AGENCY", "SOURCE_PLATFORM", "OTHER")

# 采购事件生命周期（任务书 T08.1 第五节）
PROCUREMENT_LIFECYCLE = (
    "ANNOUNCED", "OPEN", "BIDDING", "CLOSED", "AWARDED", "CANCELLED", "EXPIRED", "UNKNOWN",
)

# 机会可行动性（任务书 T08.1 第六节）
ACTIONABILITY_STATUSES = ("ACTIONABLE_NOW", "WATCH", "HISTORICAL_SIGNAL", "NOT_ACTIONABLE", "UNKNOWN")

_AWARD_INFO_SECTION = re.compile(r"[一二三四五六七八九十]、\s*(?:中标|成交)(?:（成交）)?信息")

# ccgp 标准格式："供应商名称：X 供应商地址：... 中标（成交）金额：990.0000000（万元）"
# 兼容：包件格式 "中标金额：6,350,751.00元"、数字内夹空格 "4276000 .00元"（真实公告存在）
_SUPPLIER_DECL_PATTERN = re.compile(r"供应商名称[：:]\s*([^\s，,。；;]{4,80})")
_AMOUNT_NUMBER = r"([\d,，][\d,，\s]*(?:\s*[.。]\s*\d+)?)"
_SUPPLIER_AMOUNT_AFTER = re.compile(
    r"(?:中标|成交)(?:（成交）)?金额[：:]\s*" + _AMOUNT_NUMBER + r"\s*[（(]?(万元|元)[)）]?"
)
# 折扣/下浮率（服务类，无总价时只有折扣率，如燃油供应项目）："折扣率(%)：95.7000000" / "下浮率(%)：3.0000000"
_DISCOUNT_RATE_PATTERN = re.compile(r"(?:下浮率|折扣率)\s*[（(]%[）)]?[：:]\s*([\d.]+)")
_TOTAL_AWARD_PATTERN = re.compile(r"总(?:中标|成交)金额\s*[￥¥]?\s*([\d,，][\d,，\s]*(?:\s*[.。]\s*\d+)?)\s*万?元")
_PROCUREMENT_METHOD_PATTERN = re.compile(r"(?:采购方式|招标方式)[：:]\s*([^\s，,。；;]{2,20})")
_AGENCY_NAME_PATTERN = re.compile(r"代理机构名称[：:]\s*([^\s，,。；;（(]{4,80})")
_EXECUTING_AGENCY_PATTERN = re.compile(r"采购执行机构信息\s*名\s*称[：:]\s*([^\s，,。；;（(]{4,80})")
_CANCELLED_PATTERN = re.compile(r"(废标|终止采购|项目取消|取消采购|流标)")


def _to_yuan(amount: float, unit: str | None) -> float:
    return round(amount * 10000, 2) if unit and "万" in unit else round(amount, 2)


def _parse_amount_number(raw: str) -> float | None:
    """金额数字规范化（真实公告存在"4276000 .00"式空格与全角逗号）。"""
    cleaned = raw.replace(" ", "").replace("，", "").replace(",", "").replace("。", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_awarded_suppliers_with_amounts(text: str | None) -> list[dict]:
    """解析中标（成交）信息：每家供应商 + 对应金额（统一折算为元）。

    支持 ccgp 真实三种格式：
    1. 单/多供应商："供应商名称：X ... 中标（成交）金额：N（万元）"
    2. 包件格式："包件 1 供应商名称：X ... 中标金额：6,350,751.00元"
    3. 仅折扣率（服务类，无总价）：金额 None、amount_source=DISCOUNT_RATE_ONLY
    原文无金额 → None；禁止用"总中标金额"冒充单家供应商金额。
    """
    if not text:
        return []
    body = text[:20000]

    # 中标（成交）信息章节优先（避免误抓"主要标的信息"表格里的供应商名）
    section_match = _AWARD_INFO_SECTION.search(body)
    section = body[section_match.start():] if section_match else body

    suppliers: list[dict] = []
    seen: set[str] = set()
    decl_matches = list(_SUPPLIER_DECL_PATTERN.finditer(section))
    for i, decl in enumerate(decl_matches):
        raw_name = decl.group(1).strip()
        cleaned = re.split(r"(?:项目名称|采购人|中标金额|地址|电话)", raw_name)[0].strip("：: ，,。；;")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        window_end = decl_matches[i + 1].start() if i + 1 < len(decl_matches) else min(len(section), decl.end() + 400)
        window = section[decl.end():window_end]
        amount: float | None = None
        amount_raw: str | None = None
        amount_match = _SUPPLIER_AMOUNT_AFTER.search(window)
        if amount_match:
            number = _parse_amount_number(amount_match.group(1))
            if number is not None:
                amount = _to_yuan(number, amount_match.group(2))
                amount_raw = re.sub(r"\s+", "", amount_match.group(0))
        suppliers.append({
            "supplier_name": cleaned,
            "award_amount": amount,
            "currency": "CNY" if amount is not None else None,
            "amount_raw": amount_raw,
            "discount_rate": None,
        })

    if not suppliers:
        return []

    # 金额缺失时补充项目级线索（总金额只作 total 标注，不并入单家供应商）
    if all(s["award_amount"] is None for s in suppliers):
        discount = _DISCOUNT_RATE_PATTERN.search(section)
        total = parse_total_award_amount(body)  # 为 0（￥0.000000）视为无金额
        for s in suppliers:
            if discount:
                s["discount_rate"] = float(discount.group(1))
                s["amount_source"] = "DISCOUNT_RATE_ONLY"
            elif total:
                s["amount_source"] = "TOTAL_ONLY"
                s["total_award_amount"] = total
    return suppliers


def parse_total_award_amount(text: str | None) -> float | None:
    """公告级"总中标/成交金额"（￥N 万元），统一折算为元；解析不到或为 0（如仅折扣率项目）返回 None。"""
    if not text:
        return None
    match = _TOTAL_AWARD_PATTERN.search(text[:20000])
    if not match:
        return None
    number = _parse_amount_number(match.group(1))
    if number is None:
        return None
    amount = round(number * 10000, 2)
    return amount if amount > 0 else None


def parse_procurement_method(text: str | None) -> str | None:
    """采购方式：仅取显式"采购方式/招标方式："字段（评审专家名单中的
    "单一来源采购人员"是 ccgp 固定模板，不得据此判定单一来源）。"""
    if not text:
        return None
    match = _PROCUREMENT_METHOD_PATTERN.search(text[:20000])
    return match.group(1).strip() if match else None


def parse_buyer_organization(text: str | None) -> dict:
    """采购方（Buyer）：优先"采购人信息 名 称"（法人），其次 ccgp 表格"采购单位 X 行政区域"，
    再次"采购人：X"。同时单独返回采购执行机构（存在时），二者不得混同。
    同一主体以更完整名称为准（如"上海国际旅行卫生保健中心（上海海关口岸门诊部）"）。"""
    body = text[:20000] if text else ""
    info_name = None
    match = _INFO_PURCHASER_PATTERN.search(body)
    if match:
        info_name = match.group(1).strip()
    table_name = None
    match = _TABLE_PURCHASER_PATTERN.search(body)
    if match:
        table_name = match.group(1).strip()
    plain_name = None
    match = _PURCHASER_NAME_PATTERN.search(body)
    if match:
        plain_name = match.group(1).strip()

    def _prefer(full: str | None, short: str | None) -> str | None:
        if full and short and short.startswith(f"{full}（"):
            return short  # 表格值只是法人名+括号别名（更完整）
        return full or short

    buyer = _prefer(info_name, table_name) or plain_name
    executing = None
    exec_match = _EXECUTING_AGENCY_PATTERN.search(body)
    if exec_match:
        executing = exec_match.group(1).strip()
    if executing is None and table_name and buyer and table_name != buyer and not table_name.startswith(f"{buyer}（"):
        # 表格"采购单位"与采购人法人不一致 → 它是采购执行机构（如 海关总署→海关总署物资装备采购中心）
        executing = table_name
    agency = None
    agency_match = _AGENCY_NAME_PATTERN.search(body)
    if agency_match:
        agency = agency_match.group(1).strip()
    return {"buyer": buyer, "executing_agency": executing, "procurement_agency": agency}


def parse_procurement_lifecycle(
    text: str | None,
    *,
    deadline: datetime | None = None,
    now: datetime | None = None,
) -> str:
    """采购事件生命周期（任务书第五节）：
    - 中标/成交结果公告 → AWARDED（合同已授予 ≠ 正在寻找供应商）；
    - 废标/流标/终止 → CANCELLED；
    - 招标/采购公告 + 截止时间未到 → OPEN；已过 → CLOSED；
    - 采购公告但无截止时间 → ANNOUNCED；其余 → UNKNOWN。
    """
    if not text:
        return "UNKNOWN"
    body = text[:20000]
    if _CANCELLED_PATTERN.search(body):
        return "CANCELLED"
    if re.search(r"(中标（成交）信息|中标结果公告|成交结果公告|中标公告|成交公告|中标信息)", body):
        return "AWARDED"
    if deadline is not None:
        now = now or datetime.now()
        deadline_naive = deadline.replace(tzinfo=None) if deadline.tzinfo else deadline
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now
        return "OPEN" if deadline_naive >= now_naive else "CLOSED"
    if re.search(r"(公开招标公告|采购公告|磋商公告|询价公告|招标公告)", body):
        return "ANNOUNCED"
    return "UNKNOWN"


def classify_subject_role(
    subject_name: str | None,
    buyer_info: dict,
    awarded_suppliers: list[dict],
) -> str:
    """主体角色判定（任务书第三节：采购方与中标方绝对不能混）。
    主体是中标供应商 → SUPPLIER；是采购人/执行机构 → BUYER；是代理机构 → PROCUREMENT_AGENCY；
    都不是 → OTHER（不猜）。"""
    name = "".join((subject_name or "").lower().split())
    if not name:
        return "OTHER"
    for s in awarded_suppliers:
        if "".join(s["supplier_name"].lower().split()) == name:
            return "SUPPLIER"
    for key in ("buyer", "executing_agency"):
        org = buyer_info.get(key)
        if org and "".join(str(org).lower().split()) == name:
            return "BUYER"
    agency = buyer_info.get("procurement_agency")
    if agency and "".join(str(agency).lower().split()) == name:
        return "PROCUREMENT_AGENCY"
    return "OTHER"


def derive_actionability(procurement_status: str, subject_role: str) -> str:
    """可行动性（任务书第六/七节）：
    - AWARDED：对"参与当前采购"不可行动；供应商侧保留为历史能力证据（HISTORICAL_SIGNAL），
      采购方侧计入采购历史（NOT_ACTIONABLE）；
    - OPEN（招标未截止）：ACTIONABLE_NOW；
    - ANNOUNCED（无截止时间）：WATCH；
    - CLOSED/EXPIRED/CANCELLED：NOT_ACTIONABLE。
    """
    if procurement_status == "AWARDED":
        return "HISTORICAL_SIGNAL" if subject_role == "SUPPLIER" else "NOT_ACTIONABLE"
    if procurement_status == "OPEN":
        return "ACTIONABLE_NOW"
    if procurement_status == "ANNOUNCED":
        return "WATCH"
    if procurement_status in {"CLOSED", "EXPIRED", "CANCELLED"}:
        return "NOT_ACTIONABLE"
    return "UNKNOWN"


def extract_award_evidence_snippet(text: str | None, supplier_name: str, *, max_chars: int = 260) -> str | None:
    """从原文截取能同时证明"供应商名称"与"中标金额"的精确子串（Evidence 引用）。

    返回值保证是原文精确子串（可用 text.find 还原 offset 高亮）；找不到返回 None。
    """
    if not text or not supplier_name:
        return None
    idx = text.find(f"供应商名称：{supplier_name}")
    if idx < 0:
        idx = text.find(supplier_name)
        if idx < 0:
            return None
        # 回退：从主体名第一次出现处取样（仍是精确子串）
        snippet = text[max(0, idx - 20):idx + max_chars]
        return _trim_to_sentence(snippet) or None
    amount_match = _SUPPLIER_AMOUNT_AFTER.search(text, idx)
    if amount_match and amount_match.start() <= idx + max_chars:
        snippet = text[idx:amount_match.end()]
    else:
        snippet = _trim_to_sentence(text[idx:idx + max_chars])
    return snippet or None


def _trim_to_sentence(snippet: str, *, min_len: int = 40) -> str:
    """无金额时按最后一句读符号截断，避免引用在词中间断开；仍是精确子串。"""
    pos = max(snippet.rfind("。"), snippet.rfind("；"))
    if pos >= min_len:
        return snippet[:pos + 1]
    return snippet
