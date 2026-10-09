"""T08.1 回归：来源平台绝不能成为业务企业（SOURCE_PLATFORM ≠ Company 主体）。"""
import pytest
from sqlalchemy import select

from app.core.constants import is_source_platform_domain
from app.db.session import SessionLocal
from app.models.company import Company
from app.services.company_discovery import upsert_discovered_company


def test_major_platform_domains_blacklisted():
    for host in (
        "www.ccgp.gov.cn", "ccgp.gov.cn", "search.ccgp.gov.cn", "ccgp.cn",
        "www.zhaopin.com", "www.51job.com", "www.liepin.com", "www.gov.cn",
        "news.sina.com.cn", "www.36kr.com", "www.thepaper.cn",
    ):
        assert is_source_platform_domain(host), host


def test_business_domain_not_blacklisted():
    assert not is_source_platform_domain("www.hanbang-laser.example.com")
    assert not is_source_platform_domain("www.feimian-tech.example.cn")
    assert not is_source_platform_domain("")


def test_platform_organization_type_not_created_via_upsert_gate():
    """upsert Gate：来源平台类型的主体不得进入正式企业池。"""
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            upsert_discovered_company(
                db, name="中国政府采购网", source_url="https://www.ccgp.gov.cn/x.htm",
                organization_type="SOURCE_PLATFORM",
            )


def test_no_active_source_platform_company_in_pool():
    """正式库（测试库）ACTIVE 企业池内不得有 SOURCE_PLATFORM 主体。"""
    with SessionLocal() as db:
        platforms = db.scalars(select(Company).where(
            Company.organization_type == "SOURCE_PLATFORM",
            Company.status == "ACTIVE",
        )).all()
        assert platforms == []


def test_platform_org_type_is_recognizable_for_flagging():
    """历史遗留的平台主体（若存在）必须可被识别并排除出业务统计（非 ACTIVE 状态）。"""
    with SessionLocal() as db:
        rows = db.scalars(select(Company).where(Company.organization_type == "SOURCE_PLATFORM")).all()
        for c in rows:
            assert c.status != "ACTIVE", f"平台主体 {c.company_name} 仍在 ACTIVE 业务池"
