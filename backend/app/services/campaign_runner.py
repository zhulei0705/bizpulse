"""T08 采集战役执行管线（Discover → Fetch → Normalize → Resolve → Store → Signal）。

- 每一步独立失败：单条公告失败不回滚整批（任务书三十一）；
- 限速 + 同域限制 + 不绕过 403（任务书五十三）；
- 中标供应商从真实公告正文提取（不猜测），Company 入库走 Gate（upsert_discovered_company）；
- Signal 一律 VALID 待人工批准，不自动批准（任务书三十二）；
- 复用 T03 的 content_hash 去重/版本机制，不实现第二套（任务书二十九）。
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import CollectionCampaign
from app.models.company import Company
from app.models.signal import Signal
from app.services import extractor
from app.services.company_discovery import extract_awarded_suppliers, upsert_discovered_company
from app.services.company_quality import refresh_company_quality
from app.services.ingest import create_rule_signals, get_manual_source

logger = logging.getLogger(__name__)

FETCH_DELAY_SECONDS = 1.2
_DETAIL_HREF_PATTERN = re.compile(r"/cggg/(?:[a-z]+/)+\d{6}/t\d{8}_\d+\.htm$")


def _extract_detail_links(html: str, base_url: str, host: str, limit: int) -> list[str]:
    """从列表页解析同域公告详情链接（ccgp 结果公告模式；通用化为同域 .htm 细节页）。"""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        raw = anchor["href"].strip()
        if not raw or raw.startswith(("javascript:", "#")):
            continue
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        if parsed.netloc != host:
            continue
        if not (_DETAIL_HREF_PATTERN.search(parsed.path) or re.search(r"t\d{8}_\d+\.htm$", parsed.path)):
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)
        if len(links) >= limit:
            break
    return links


def _organization_type_from_notice(notice_text: str, supplier_name: str) -> str:
    """组织类型判断：仅依据真实上下文规则（中标供应商默认商业企业；无法确认 UNKNOWN）。"""
    name = supplier_name or ""
    if any(k in name for k in ("大学", "学院")):
        return "UNIVERSITY"
    if any(k in name for k in ("研究院", "研究所", "科学院")):
        return "RESEARCH_INSTITUTE"
    if any(k in name for k in ("医院",)):
        return "HOSPITAL"
    if any(k in name for k in ("有限公司", "股份", "集团", "公司")):
        return "COMPANY"
    if re.search(r"政府|管理局|委员会|财政", notice_text[:200] or ""):
        return "GOVERNMENT"
    return "UNKNOWN"


def run_campaign(db: Session, campaign: CollectionCampaign, *, max_notices: int = 40) -> dict:
    """执行采集战役：真实抓取公告 → 提取中标供应商 → 企业入池 + CONTRACT_AWARD 信号。"""
    campaign.status = "RUNNING"
    campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
    db.commit()

    manual_source = get_manual_source(db)
    progress = {
        "seed_urls": list(campaign.seed_urls or []),
        "notices_fetched": 0,
        "suppliers_found": 0,
        "companies_created": 0,
        "companies_duplicate": 0,
        "signals_created": 0,
        "errors": [],
        "finished": False,
    }
    target_total = int(campaign.target_company_count or 30)
    supplier_seen: set[str] = set()

    try:
        for seed_url in list(campaign.seed_urls or []):
            if progress["companies_created"] >= target_total:
                break
            try:
                page = extractor.fetch_public_page(seed_url)
            except Exception as exc:  # noqa: BLE001 - 单个 seed 失败不中断
                progress["errors"].append(f"seed_fetch_failed {seed_url}: {str(exc)[:120]}")
                continue
            host = urlparse(page.final_url).netloc
            detail_links = _extract_detail_links(page.html, page.final_url, host, max_notices)
            for link in detail_links:
                if progress["companies_created"] >= target_total:
                    break
                try:
                    notice = extractor.fetch_public_page(link)
                except Exception as exc:  # noqa: BLE001
                    progress["errors"].append(f"notice_fetch_failed {link}: {str(exc)[:120]}")
                    time.sleep(FETCH_DELAY_SECONDS)
                    continue
                progress["notices_fetched"] += 1
                try:
                    # 1) 公告本身作为 SourceRecord（复用 ingest 链路的去重/版本/企业关联）
                    from app.collectors.base import CollectedItem
                    from app.collectors.web import parse_published_raw
                    from app.services.collection_engine import persist_collected
                    from app.services.procurement_parser import (
                        extract_procurement_contacts,
                        parse_announcement_time,
                        parse_deadline,
                        parse_budget_amount,
                        parse_purchaser,
                        parse_project_name,
                        parse_category,
                    )

                    announcement_time = parse_announcement_time(notice.text)
                    deadline = parse_deadline(notice.text)
                    fields = {
                        "announcement_time": announcement_time.isoformat() if announcement_time else None,
                        "deadline": deadline.isoformat() if deadline else None,
                        "budget_amount": parse_budget_amount(notice.text),
                        "purchaser": parse_purchaser(notice.text),
                        "project_name": parse_project_name(notice.text),
                        "category": parse_category(notice.text),
                    }
                    item = CollectedItem(
                        url=notice.final_url,
                        canonical_url=notice.final_url,
                        title=notice.title,
                        raw_text=notice.text,
                        # P0-5：published_at 必须来自公告发布时间；缺失 fallback collected_at 并标记
                        published_at=announcement_time or parse_published_raw(notice.published_at_raw),
                        http_status=notice.status_code,
                        content_type=notice.content_type,
                        language="zh",
                        extra={
                            "procurement_fields": {k: v for k, v in fields.items() if k != "contacts"},
                            "freshness_source": "ANNOUNCEMENT_TIME" if announcement_time else "COLLECTED_AT_FALLBACK",
                        },
                    )
                    record, outcome = persist_collected(db, manual_source, item)
                    # P0-5：freshness_source 标记（published_at 缺失时 fallback collected_at 必须可见）
                    record.metadata_json = {**(record.metadata_json or {}),
                                            "freshness_source": item.extra.get("freshness_source"),
                                            "procurement_fields": item.extra.get("procurement_fields")}
                    if outcome == "SKIPPED_UNCHANGED":
                        time.sleep(FETCH_DELAY_SECONDS)
                        continue

                    # 2) 提取中标供应商（真实正文；提不到就跳过，不猜测）
                    suppliers = extract_awarded_suppliers(notice.text)
                    for supplier in suppliers:
                        name = supplier["name"]
                        if name in supplier_seen:
                            continue
                        supplier_seen.add(name)
                        org_type = _organization_type_from_notice(notice.text, name)
                        company, created = upsert_discovered_company(
                            db, name=name, source_url=notice.final_url,
                            source_title=notice.title, organization_type=org_type,
                        )
                        progress["companies_created" if created else "companies_duplicate"] += 1
                        # 3) 公告关联到供应商企业（而非 ccgp 域名残留）
                        record.company_id = company.id
                        record.company_resolve_status = "EXACT"
                        # 4) CONTRACT_AWARD 信号：真实商业事实，VALID 待人工批准
                        existing_signal = db.scalar(select(Signal).where(
                            Signal.company_id == company.id,
                            Signal.source_record_id == record.id,
                            Signal.signal_type == "CONTRACT_AWARD",
                        ))
                        if existing_signal is None:
                            signal = Signal(
                                company_id=company.id,
                                source_record_id=record.id,
                                signal_type="CONTRACT_AWARD",
                                title=f"中标：{company.company_name}（{notice.title or '采购公告'}）"[:500],
                                fact_summary=f"公开中标公告显示，{company.company_name}中标项目（来源：{notice.final_url[:120]}）",
                                description=(notice.text or "")[:500],
                                published_at=record.published_at,
                                collected_at=datetime.now(timezone.utc),
                                confidence=85,
                                status="REVIEW",
                                fact_or_inference="FACT",
                                payload_json={"extractor": "campaign_v1", "matched": supplier["matched"]},
                            )
                            db.add(signal)
                            db.flush()
                            progress["signals_created"] += 1
                        refresh_company_quality(db, company)

                    # P0-6：结构化联系人入库（采购人/代理机构/项目联系人严格区分，归属正确主体）
                    if fields.get("purchaser"):
                        from app.models.company import CompanyContact

                        purchaser_name = fields["purchaser"]
                        purchaser_company = db.scalar(select(Company).where(
                            Company.normalized_name == "".join(purchaser_name.lower().split())))
                        if purchaser_company is None:
                            # 采购单位是采购事件的业务主体：不存在则创建（来源=公告 URL）
                            purchaser_company, _created = upsert_discovered_company(
                                db, name=purchaser_name, source_url=notice.final_url,
                                source_title=notice.title,
                                organization_type=_organization_type_from_notice(notice.text, purchaser_name),
                            )
                            progress["companies_created" if _created else "companies_duplicate"] += 1
                        if purchaser_company is not None:
                            for draft in extract_procurement_contacts(notice.text):
                                existing_contact = db.scalar(select(CompanyContact).where(
                                    CompanyContact.company_id == purchaser_company.id,
                                    CompanyContact.source_url == notice.final_url,
                                    CompanyContact.contact_type == draft.contact_type,
                                ))
                                if existing_contact is not None:
                                    continue
                                db.add(CompanyContact(
                                    company_id=purchaser_company.id,
                                    name=draft.name,
                                    phone=draft.phone,
                                    email=draft.email,
                                    public_contact=draft.phone or draft.email,
                                    contact_type=draft.contact_type,
                                    organization_name=draft.organization_name or purchaser_name,
                                    source_url=notice.final_url,
                                    source_type="OFFICIAL_WEBSITE",
                                    verification_status="VERIFIED_PUBLIC",
                                    confidence=80,
                                ))
                                progress["contacts_created"] = progress.get("contacts_created", 0) + 1
                            db.flush()

                    db.commit()
                except Exception as exc:  # noqa: BLE001 - 单条公告失败不回滚整批
                    db.rollback()
                    progress["errors"].append(f"notice_process_failed {link}: {str(exc)[:150]}")
                time.sleep(FETCH_DELAY_SECONDS)
            time.sleep(FETCH_DELAY_SECONDS)
    finally:
        progress["finished"] = True
        campaign.progress_json = progress
        # 未达目标保持 RUNNING（可再次 run 继续扩充）；达标 COMPLETED
        if progress["companies_created"] >= target_total:
            campaign.status = "COMPLETED"
            campaign.completed_at = datetime.now(timezone.utc)
        db.commit()

    return {"campaign_id": campaign.id, "status": campaign.status, **progress}
