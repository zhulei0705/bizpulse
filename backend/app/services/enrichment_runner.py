"""T08.2 企业数据深挖执行器（任务书三十五/三十六）。

单企业管线：Website Discovery → Fetch → 页面分类 → SourceRecord 入库
→ Signal 规则分析（真实正文+证据门）→ Contact 抽取（禁止猜邮箱）→ 覆盖刷新。

原则：
- 只抓官方域名内部链接，限速，不绕过任何访问控制；
- 所有产出必须挂真实来源（source_record_id / source_url）；
- 单页失败不中断（记录留痕）；同内容指纹去重复用 collection 机制；
- 信号一律 VALID 待人工审核，不自动批准。
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.services import extractor
from app.services.actionability import record_signal_actionability
from app.services.company_discovery import (
    discover_website_sections,
    classify_page_type,
)
from app.services.company_quality import refresh_company_quality
from app.services.contact_extractor import (
    classify_contact_page,
    extract_contacts,
    site_domain_of,
)
from app.services.audit import write_audit

FETCH_DELAY = 1.2
DEFAULT_MAX_PAGES = 12

_SOURCE_BY_DIMENSION: dict[str, tuple[str, str]] = {
    "HOME": ("OFFICIAL_WEBSITE", "企业官网采集"),
    "ABOUT": ("OFFICIAL_WEBSITE", "企业官网采集"),
    "PRODUCT": ("OFFICIAL_WEBSITE", "企业官网采集"),
    "SOLUTION": ("OFFICIAL_WEBSITE", "企业官网采集"),
    "CONTACT": ("OFFICIAL_WEBSITE", "企业官网采集"),
    "NEWS_INDEX": ("OFFICIAL_NEWS", "企业官方新闻"),
    "NEWS_ARTICLE": ("OFFICIAL_NEWS", "企业官方新闻"),
    "CAREERS": ("OFFICIAL_CAREERS", "企业官方招聘"),
    "JOB_DETAIL": ("OFFICIAL_CAREERS", "企业官方招聘"),
}


def _get_or_create_source(db: Session, source_type: str, name: str) -> Source:
    src = db.scalar(select(Source).where(Source.source_type == source_type))
    if src is None:
        src = Source(name=name, source_type=source_type, reliability_grade="B",
                     reliability_score=75, enabled=True, collector_type="web_page",
                     notes="T08.2 官网深挖采集（官方域名内部页面，真实抓取）")
        db.add(src)
        db.flush()
    return src


def _persist_page(db: Session, company: Company, page, page_type: str) -> tuple[SourceRecord, str]:
    """页面入库（指纹去重/版本沿用 collection 语义，但企业关联显式指定，不做自动解析）。"""
    source_type, source_name = _SOURCE_BY_DIMENSION.get(page_type, ("OFFICIAL_WEBSITE", "企业官网采集"))
    source = _get_or_create_source(db, source_type, source_name)
    fingerprint = hashlib.sha256(
        f"{page.final_url}\n{page.title or ''}\n{(page.text or '')[:2000]}".encode("utf-8")).hexdigest()
    existing = db.scalar(select(SourceRecord).where(
        SourceRecord.source_id == source.id, SourceRecord.content_hash == fingerprint))
    if existing is not None:
        return existing, "SKIPPED_UNCHANGED"
    record = SourceRecord(
        source_id=source.id, company_id=company.id, url=page.final_url, canonical_url=page.final_url,
        title=page.title, raw_text=(page.text or "")[:60_000], content_hash=fingerprint,
        http_status=page.status_code, content_type=page.content_type, language="zh",
        source_reliability=source.reliability_grade, verification_status="VERIFIED",
        last_verified_at=datetime.now(timezone.utc), company_resolve_status="EXACT",
        metadata_json={"collected_via": "t082_enrichment", "page_type": page_type},
    )
    db.add(record)
    db.flush()
    company.source_count = (company.source_count or 0) + 1
    write_audit(db, "T082_PAGE_COLLECTED", "source_record", record.id,
                {"company_id": company.id, "url": page.final_url, "page_type": page_type})
    return record, "CREATED"


def _extract_jobs(text: str) -> dict:
    """招聘页结构化信息（岗位数量/线索；仅统计真实列表条目）。"""
    import re

    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    job_lines = [ln for ln in lines if re.search(r"(工程师|专员|经理|主管|总监|助理|顾问|代表|操作员|设计师|分析师|销售|客服|会计)", ln) and len(ln) <= 60]
    locations = sorted({m.group(1) for ln in job_lines for m in [re.search(r"(北京|上海|广州|深圳|杭州|苏州|南京|武汉|成都|西安|长沙|郑州|青岛|宁波|无锡|昆山|厦门|天津|重庆|东莞|佛山|珠海|中山|惠州|嘉兴|常州|南通|合肥|福州|济南|大连|沈阳)", ln)] if m})
    return {"job_entry_count": len(job_lines), "locations": locations[:20]}


def _signals_from_record(db: Session, company: Company, record: SourceRecord, page_type: str) -> list[Signal]:
    """对真实正文跑规则引擎（复用 create_rule_signals 语义），并写 actionability。"""
    from app.services import extractor as ext
    from app.services.ingest import _source_score

    page_like = ext.FetchedPage(
        url=record.url, final_url=record.url, status_code=record.http_status or 200,
        content_type=record.content_type, title=record.title,
        text=record.raw_text or "", html="",
    )
    hits = ext.extract_signal_hits(page_like)
    # 同企业同类型同证据去重（多次采集/重复页面不重复生成）
    existing = {
        (s.signal_type, (s.description or "")[:60])
        for s in db.scalars(select(Signal).where(Signal.company_id == company.id)).all()
    }
    signals = []
    for hit in hits:
        if (hit.signal_type, (hit.excerpt or "")[:60]) in existing:
            continue
        existing.add((hit.signal_type, (hit.excerpt or "")[:60]))
        signal = Signal(
            company_id=company.id, source_record_id=record.id,
            signal_type=hit.signal_type,
            title=f"{hit.title}：{record.title or record.url[:80]}"[:500],
            description=hit.excerpt,
            published_at=record.published_at,
            collected_at=datetime.now(timezone.utc),
            confidence=hit.confidence,
            reliability_score=_source_score(db, record.source_id),
            status="REVIEW", fact_or_inference="FACT",
            payload_json={
                "extractor": "t082_enrichment_v1",
                "page_type": page_type,
                "excerpt": hit.excerpt,
            },
        )
        db.add(signal)
        db.flush()
        record_signal_actionability(db, signal)
        signals.append(signal)
    if signals:
        write_audit(db, "CREATE", "signal", signals[0].id,
                    {"count": len(signals), "via": "t082_enrichment", "source_record_id": record.id})
    return signals


def _contacts_from_record(db: Session, company: Company, record: SourceRecord, page_type: str) -> list[CompanyContact]:
    """联系渠道入库（原文直接公开才收；is_decision_maker 一律 False）。"""
    from app.services.evidence_quality import extract_valid_evidence  # noqa: F401  保持证据口径一致

    domain = site_domain_of(company.website or record.url)
    # WEBSITE_FORM 只认联系页（任务书十九：官方联系表单；导航里的"在线留言"链接不算）
    is_contact_page = page_type == "CONTACT"
    drafts = extract_contacts(
        record.raw_text, page_url=record.url, company_domain=domain, page_is_contact=is_contact_page)
    created = []
    for d in drafts:
        dup = None
        if d.channel == "EMAIL" and d.email:
            dup = db.scalar(select(CompanyContact).where(
                CompanyContact.company_id == company.id, CompanyContact.email == d.email))
        elif d.channel == "PHONE" and d.phone:
            dup = db.scalar(select(CompanyContact).where(
                CompanyContact.company_id == company.id, CompanyContact.phone == d.phone))
        elif d.channel == "WEBSITE_FORM":
            dup = db.scalar(select(CompanyContact).where(
                CompanyContact.company_id == company.id, CompanyContact.public_profile_url == d.form_url))
        if dup is not None:
            continue
        contact = CompanyContact(
            company_id=company.id,
            name=d.name, title=d.title, department=d.department,
            email=d.email, phone=d.phone,
            public_contact=d.email or d.phone,
            public_profile_url=d.form_url,
            contact_type=d.contact_type,
            organization_name=company.company_name,
            source_url=record.url, source_record_id=record.id,
            source_type="OFFICIAL_WEBSITE",
            verification_status="VERIFIED_PUBLIC",  # 网页原文直接公开（抽取器保证原文存在）
            verified_public=True,
            is_decision_maker=False,  # 禁止无依据升级（任务书二十一）
            confidence=80,
        )
        db.add(contact)
        db.flush()
        write_audit(db, "T082_CONTACT_CREATED", "company_contact", contact.id,
                    {"company_id": company.id, "channel": d.channel, "contact_type": d.contact_type,
                     "email": d.email, "phone": d.phone, "form_url": d.form_url,
                     "source_url": record.url})
        created.append(contact)
    return created


def enrich_company(db: Session, company: Company, *, max_pages: int = DEFAULT_MAX_PAGES) -> dict:
    """单企业深挖（幂等：指纹/联系渠道去重）。"""
    summary: dict = {
        "company_id": company.id, "company_name": company.company_name,
        "website": company.website, "pages_found": 0, "pages_fetched": 0,
        "records_created": 0, "records_skipped": 0, "fetch_errors": [],
        "signals_created": 0, "contacts_created": 0,
        "page_types": {}, "job_insights": {},
    }
    if not company.website:
        summary["error"] = "官网未知：需先完成官网发现/验证（禁止猜测域名）"
        return summary

    try:
        home = extractor.fetch_public_page(company.website)
    except Exception as exc:  # noqa: BLE001
        summary["error"] = f"homepage_fetch_failed: {str(exc)[:150]}"
        return summary
    time.sleep(FETCH_DELAY)

    sections = discover_website_sections(company.website, max_pages=max_pages)
    summary["pages_found"] = len(sections.pages)

    pages: list = [(home.final_url, home, "HOME")]
    seen_urls = {home.final_url}
    for p in sections.pages:
        if p.url in seen_urls:
            continue
        seen_urls.add(p.url)
        pages.append((p.url, None, p.dimension))

    for url, prefetched, dimension in pages[:max_pages]:
        page_type = {
            "ABOUT": "ABOUT", "NEWS": "NEWS_INDEX", "CAREERS": "CAREERS",
            "CONTACT": "CONTACT", "PRODUCTS": "PRODUCT", "SOLUTIONS": "SOLUTION",
            "HOME": "HOME",
        }.get(dimension, "OTHER")
        try:
            page = prefetched or extractor.fetch_public_page(url)
            if prefetched is None:
                time.sleep(FETCH_DELAY)
        except Exception as exc:  # noqa: BLE001
            summary["fetch_errors"].append(f"{url}: {str(exc)[:100]}")
            continue
        if page.status_code != 200 or not (page.text or "").strip():
            summary["fetch_errors"].append(f"{url}: empty_or_{page.status_code}")
            continue
        page_type = classify_page_type(page.final_url, page.title, page.text) if page_type in {"HOME", "OTHER"} else page_type
        summary["pages_fetched"] += 1
        summary["page_types"][page_type] = summary["page_types"].get(page_type, 0) + 1

        record, outcome = _persist_page(db, company, page, page_type)
        if outcome == "CREATED":
            summary["records_created"] += 1
            signals = _signals_from_record(db, company, record, page_type)
            summary["signals_created"] += len(signals)
            contacts = _contacts_from_record(db, company, record, page_type)
            summary["contacts_created"] += len(contacts)
            if page_type == "CAREERS":
                summary["job_insights"] = _extract_jobs(record.raw_text)
        else:
            summary["records_skipped"] += 1

    refresh_company_quality(db, company)
    db.commit()
    return summary
