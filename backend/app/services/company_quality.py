"""T08 企业数据质量 / 信号新鲜度 / Source Coverage（全部代码计算，不用 LLM 打分）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.signal import Signal
from app.models.source import SourceRecord

_HIRING_TYPES = {"HIRING", "SALES_HIRING", "AI_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING"}
_PROCUREMENT_TYPES = {"PROCUREMENT", "TENDER", "CONTRACT_AWARD", "SUPPLIER_SEARCH"}
_NEWS_KEYWORDS = ("news", "xinwen", "新闻", "动态", "公告")
_CAREER_KEYWORDS = ("career", "jobs", "recruit", "招聘", "人才")


def signal_density(db: Session, company_id: str) -> dict[str, int]:
    """企业信号密度（T05 重要输入）：APPROVED+REVIEW 信号的 7/30/90 天计数。"""
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Signal).where(
        Signal.company_id == company_id,
        Signal.status.in_(["APPROVED", "REVIEW", "VALID"]),
    )).all()
    def _within(days: int) -> int:
        count = 0
        for s in rows:
            collected = s.collected_at
            if collected and collected.tzinfo is None:
                collected = collected.replace(tzinfo=timezone.utc)
            if collected and (now - collected) <= timedelta(days=days):
                count += 1
        return count
    return {"signals_7d": _within(7), "signals_30d": _within(30), "signals_90d": _within(90)}


def freshness_bucket(collected_at: datetime | None) -> str:
    """信号新鲜度分桶（0-7 / 8-30 / 31-90 / 90+ 天）。"""
    if collected_at is None:
        return "STALE"
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - collected_at).days
    if age <= 7:
        return "FRESH_7D"
    if age <= 30:
        return "RECENT_30D"
    if age <= 90:
        return "AGING_90D"
    return "STALE"


def source_coverage(db: Session, company_id: str) -> dict:
    """Source Coverage（任务书二十六/二十七）：官网/招聘/新闻/采购/联系人覆盖。

    动态聚合，不新增表；用于区分"数据不足"还是"确实没有 Signal"。
    """
    company = db.get(Company, company_id)
    if company is None:
        return {}
    records = db.scalars(select(SourceRecord).where(SourceRecord.company_id == company_id)).all()
    signals = db.scalars(select(Signal).where(Signal.company_id == company_id)).all()
    contacts = db.scalars(select(CompanyContact).where(CompanyContact.company_id == company_id)).all()

    signal_types = {s.signal_type for s in signals}
    record_texts = [f"{r.url or ''} {r.title or ''}".lower() for r in records]

    coverage = {
        "WEBSITE": bool(company.domain or company.website),
        "CAREERS": bool(signal_types & _HIRING_TYPES) or any(any(k in t for k in _CAREER_KEYWORDS) for t in record_texts),
        "NEWS": any(any(k in t for k in _NEWS_KEYWORDS) for t in record_texts) or bool(signal_types & {"NEW_PRODUCT", "PARTNERSHIP", "STRATEGIC_COOPERATION", "CONTRACT_AWARD"}),
        "PROCUREMENT": bool(signal_types & _PROCUREMENT_TYPES),
        "CONTACT": any(c.verification_status in {"VERIFIED_PUBLIC", "USER_PROVIDED"} for c in contacts),
    }
    return {
        "company_id": company_id,
        "coverage": coverage,
        "coverage_score": sum(1 for v in coverage.values() if v),
        "missing": [k for k, v in coverage.items() if not v],
        "record_count": len(records),
        "note": "missing 列表表示该维度尚未采集到数据（数据不足），不代表企业没有相关 Signal",
    }


def compute_data_quality(db: Session, company: Company) -> int:
    """企业数据质量分（0-100，代码计算；任务书二十一）：
    官网域名 30 + 行业明确 15 + 地区明确 15 + 组织类型确认 15 + 来源记录数 15 + 最近验证时间 10。
    """
    score = 0
    if company.domain or company.website:
        score += 30
    if company.industry:
        score += 15
    if company.country or company.province or company.city:
        score += 15
    if company.organization_type not in {"UNKNOWN", "", None}:
        score += 15
    record_count = db.scalar(
        select(__import__("sqlalchemy").func.count()).select_from(SourceRecord).where(SourceRecord.company_id == company.id)
    ) or 0
    score += min(15, record_count * 5)
    if company.verified_at:
        verified = company.verified_at if company.verified_at.tzinfo else company.verified_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - verified).days
        score += 10 if age_days <= 90 else 5
    return min(100, score)


def refresh_company_quality(db: Session, company: Company) -> int:
    company.company_data_quality = compute_data_quality(db, company)
    return company.company_data_quality
