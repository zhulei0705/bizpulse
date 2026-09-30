"""CompanyResolver：采集数据 → 企业关联（T03）。

匹配优先级（不依赖 LLM 猜测）：
1. EXACT            —— 官方域名精确匹配（Company.domain）
2. HIGH_CONFIDENCE  —— schema.org Organization 名称 / normalized_name / 已登记 alias
3. POSSIBLE         —— 仅名称模糊相近（不自动关联，进入人工确认）
4. UNKNOWN          —— 无法识别（不猜，等待人工）

只有 EXACT / HIGH_CONFIDENCE 自动关联；其余记录 company_resolve_status 供人工处理。
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyAlias
from app.models.source import SourceRecord


def _normalize_name(name: str) -> str:
    return "".join(name.lower().split())


@dataclass(frozen=True)
class ResolveResult:
    status: str  # EXACT / HIGH_CONFIDENCE / POSSIBLE / UNKNOWN
    company_id: str | None = None
    reason: str = ""


_NAME_SIMILARITY_THRESHOLD = 0.92  # 名称完全高度一致才给 POSSIBLE→自动档以下


class CompanyResolver:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _by_domain(self, domain: str | None) -> Company | None:
        if not domain:
            return None
        return self.db.scalar(select(Company).where(Company.domain == domain.lower()))

    def _by_exact_name(self, name: str | None) -> Company | None:
        if not name:
            return None
        normalized = _normalize_name(name)
        if not normalized:
            return None
        company = self.db.scalar(select(Company).where(Company.normalized_name == normalized))
        if company:
            return company
        alias = self.db.scalar(select(CompanyAlias).where(CompanyAlias.normalized_alias == normalized))
        if alias:
            return self.db.get(Company, alias.company_id)
        return None

    def _by_similar_name(self, name: str | None) -> list[Company]:
        """名称高度相近（≥0.92）的候选：仅作为 POSSIBLE，不自动关联。"""
        if not name:
            return []
        normalized = _normalize_name(name)
        if len(normalized) < 4:
            return []
        candidates: list[Company] = []
        for company in self.db.scalars(select(Company).limit(500)):
            ratio = SequenceMatcher(None, normalized, company.normalized_name).ratio()
            if ratio >= _NAME_SIMILARITY_THRESHOLD:
                candidates.append(company)
        return candidates

    def resolve(self, *, domain: str | None = None, organization_name: str | None = None) -> ResolveResult:
        # 1. 官方域名精确匹配
        company = self._by_domain(domain)
        if company:
            return ResolveResult("EXACT", company.id, f"domain={domain}")

        # 2. 明确企业名称（schema.org/OG/标题识别）精确匹配
        company = self._by_exact_name(organization_name)
        if company:
            return ResolveResult("HIGH_CONFIDENCE", company.id, f"name={organization_name}")

        # 3. 名称模糊相近 → POSSIBLE（不自动关联）
        similar = self._by_similar_name(organization_name)
        if similar:
            return ResolveResult("POSSIBLE", None, f"相近候选：{', '.join(c.company_name for c in similar[:3])}")

        return ResolveResult("UNKNOWN", None, "无可靠匹配依据，不猜测")


def domain_of_url(url: str | None) -> str | None:
    from urllib.parse import urlparse
    if not url:
        return None
    return (urlparse(url).hostname or "").lower().rstrip(".") or None


def resolve_record_company(db: Session, record: SourceRecord, organization_name: str | None) -> tuple[SourceRecord, ResolveResult]:
    """解析并回写 SourceRecord 的企业关联状态。"""
    resolver = CompanyResolver(db)
    result = resolver.resolve(domain=domain_of_url(record.url), organization_name=organization_name)
    if result.company_id and result.status in {"EXACT", "HIGH_CONFIDENCE"}:
        record.company_id = result.company_id
        record.company_resolve_status = result.status
    else:
        record.company_resolve_status = result.status if result.status != "POSSIBLE" else "POSSIBLE"
    return record, result
