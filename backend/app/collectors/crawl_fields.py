"""显式 CSS 字段抽取；格式不合法或角色不明确时返回 UNKNOWN，不补全事实。"""
from __future__ import annotations
import re
from datetime import datetime
from decimal import Decimal
from bs4 import BeautifulSoup
from app.collectors.crawl_policy import digest

FIELDS = {"published_at", "deadline", "budget", "buyer", "supplier", "agency"}


def strict_value(field: str, value: str):
    if field in {"published_at", "deadline"}:
        # 不用相邻日期猜字段；完整年月日必须由配置的字段节点提供。
        normalized = value.strip().replace("年", "-").replace("月", "-").replace("日", "")
        normalized = normalized.replace("时", ":").replace("点", ":").replace("分", "").replace("：", ":")
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
            try:
                result = datetime.strptime(normalized, fmt)
                if 2000 <= result.year <= 2100:
                    return {"value": result.isoformat(), "timezone": "UNKNOWN", "precision": "DATE" if result.hour == result.minute == 0 and " " not in normalized else "MINUTE"}
            except ValueError:
                continue
    elif field == "budget":
        match = re.fullmatch(r"(?:人民币\s*)?([0-9]+(?:\.[0-9]{1,2})?)\s*(万元|元)", value)
        if match:
            amount = Decimal(match[1]) * (10000 if match[2] == "万元" else 1)
            if 0 < amount <= Decimal("1000000000000"):
                return {"value": str(amount), "currency": "CNY"}
    elif field in {"buyer", "supplier", "agency"}:
        # 主体名称与角色必须同时来自节点；单个企业名无法证明其采购方/中标方角色。
        role = {"buyer": "采购人", "supplier": "供应商", "agency": "采购代理机构"}[field]
        match = re.fullmatch(re.escape(role) + r"[：:]\s*([^\n]{4,120})", value)
        if match and re.search(r"(?:公司|大学|学院|研究院|研究所|中心|委员会|局|医院|实验室)$", match[1]):
            return {"value": match[1], "role": field}
    return None


def extract_fields(html: str, selectors: dict | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result = {f: {"status": "UNKNOWN"} for f in sorted(FIELDS)}
    for field, selector in (selectors or {}).items():
        if field not in FIELDS or not isinstance(selector, str):
            continue
        nodes = soup.select(selector)
        if len(nodes) != 1:
            continue
        quote = nodes[0].get_text(" ", strip=True)
        value = strict_value(field, quote)
        if value:
            result[field] = {"status": "EXTRACTED_UNVERIFIED", **value, "quote": quote,
                             "basis": "DOM_NODE", "css_selector": selector, "snapshot_hash": digest(html)}
    return result
