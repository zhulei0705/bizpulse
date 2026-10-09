"""T08.2 企业覆盖审计回归（任务书四/五）：字段全量、缺口计算、真实聚合。"""
import uuid

from app.db.session import SessionLocal
from app.models.company import Company
from app.models.source import Source, SourceRecord
from app.services.company_coverage import coverage_audit_one, coverage_gap


def _mk_company(db, name, **kw) -> Company:
    c = Company(company_name=name, normalized_name=name.lower(),
                organization_type=kw.get("organization_type", "COMPANY"),
                verification_status=kw.get("verification_status", "WEBSITE_VERIFIED"),
                website=kw.get("website"), domain=kw.get("domain"),
                province=kw.get("province"))
    db.add(c)
    db.flush()
    return c


def _mk_record(db, company, url, title) -> SourceRecord:
    src = Source(name=f"覆盖测试源{uuid.uuid4().hex[:4]}", source_type="OFFICIAL_WEBSITE",
                 reliability_grade="B", reliability_score=75)
    db.add(src)
    db.flush()
    r = SourceRecord(source_id=src.id, company_id=company.id, url=url, title=title,
                     raw_text="x", content_hash=f"h-{uuid.uuid4().hex[:8]}", http_status=200)
    db.add(r)
    db.flush()
    return r


def test_coverage_audit_fields_complete():
    """审计输出包含任务书四要求的字段。"""
    with SessionLocal() as db:
        c = _mk_company(db, "覆盖字段测试公司", website="https://cover.example.com",
                        domain="cover.example.com", province="江苏省")
        db.commit()
        audit = coverage_audit_one(db, c)
    for key in (
        "company_id", "company_name", "official_website", "website_verified", "industry",
        "country", "province", "city", "homepage_covered", "news_covered", "careers_covered",
        "products_covered", "solutions_covered", "contact_covered", "procurement_covered",
        "source_record_count", "approved_signal_count", "actionable_signal_count",
        "historical_signal_count", "opportunity_count", "validation_ready", "contact_ready",
        "last_verified_at",
    ):
        assert key in audit, key


def test_coverage_dimensions_from_records():
    """URL/标题含栏目关键词 → 对应维度 covered。"""
    with SessionLocal() as db:
        c = _mk_company(db, "覆盖维度测试公司", website="https://dims.example.com", domain="dims.example.com")
        _mk_record(db, c, "https://dims.example.com/news/list.html", "新闻中心")
        _mk_record(db, c, "https://dims.example.com/jobs", "人才招聘")
        _mk_record(db, c, "https://dims.example.com/contact.html", "联系我们")
        _mk_record(db, c, "https://dims.example.com/product", "产品中心")
        db.commit()
        audit = coverage_audit_one(db, c)
    assert audit["homepage_covered"] is True
    assert audit["news_covered"] is True
    assert audit["careers_covered"] is True
    assert audit["contact_covered"] is True
    assert audit["products_covered"] is True
    assert audit["solutions_covered"] is False  # 没有解决方案页 → 如实缺口


def test_coverage_gap_priority_order():
    """缺口按商业价值优先排序：Contact > Careers > News > Products > Solutions。"""
    audit = {"contact_covered": False, "careers_covered": False, "news_covered": False,
             "products_covered": False, "solutions_covered": False, "homepage_covered": True}
    gap = coverage_gap(audit)
    assert gap == ["contact_covered", "careers_covered", "news_covered",
                   "products_covered", "solutions_covered"]


def test_full_coverage_has_empty_gap():
    with SessionLocal() as db:
        c = _mk_company(db, "全覆盖测试公司", website="https://full.example.com", domain="full.example.com")
        for url, title in [("https://full.example.com/news", "新闻中心"),
                           ("https://full.example.com/careers", "加入我们"),
                           ("https://full.example.com/contact", "联系方式"),
                           ("https://full.example.com/products", "产品中心"),
                           ("https://full.example.com/solutions", "解决方案")]:
            _mk_record(db, c, url, title)
        db.commit()
        audit = coverage_audit_one(db, c)
    assert coverage_gap(audit) == []
