"""T08.1 中标供应商 Company Discovery 回归（任务书第二十节：Supplier → Company 流程）。"""
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.company import Company
from app.services.company_discovery import extract_awarded_suppliers, upsert_discovered_company
from app.services.campaign_runner import _organization_type_from_notice

TWO_PACKAGE_NOTICE = """某项目中标公告
三、中标信息 包件 1 供应商名称：上海新一名实业（集团）有限公司 供应商地址：上海市宝山区 中标金额：6,350,751.00元 包件 2 供应商名称：德赛集团有限公司 供应商地址：温州市 中标金额：6,951,814.00元"""


def test_extract_awarded_suppliers_covers_both_packages():
    suppliers = extract_awarded_suppliers(TWO_PACKAGE_NOTICE)
    names = {s["name"] for s in suppliers}
    assert "上海新一名实业（集团）有限公司" in names
    assert "德赛集团有限公司" in names


def test_extract_ignores_buyer_and_candidates():
    text = "采购人：某大学 中标候选人第一名：某公司 中标供应商名称：真实中标公司"
    suppliers = extract_awarded_suppliers(text)
    names = {s["name"] for s in suppliers}
    assert "真实中标公司" in names
    assert "某大学" not in names


def test_extract_empty_text_returns_empty():
    assert extract_awarded_suppliers(None) == []
    assert extract_awarded_suppliers("没有中标信息的正文") == []


def test_upsert_requires_source_url():
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            upsert_discovered_company(db, name="无来源公司", source_url="")


def test_upsert_creates_public_source_verified_company():
    with SessionLocal() as db:
        company, created = upsert_discovered_company(
            db, name="探索测试科技有限公司", source_url="https://ccgp.example.com/notice/1",
            organization_type="COMPANY",
        )
        db.commit()
        assert created is True
        assert company.verification_status == "PUBLIC_SOURCE_VERIFIED"
        assert company.discovery_source_url == "https://ccgp.example.com/notice/1"
        # 二次发现同名企业 → 去重不新建（Company Resolver 规则）
        again, created_again = upsert_discovered_company(
            db, name="探索测试科技有限公司", source_url="https://ccgp.example.com/notice/2",
            organization_type="COMPANY",
        )
        db.commit()
        assert created_again is False
        assert again.id == company.id


def test_organization_type_from_notice_rules():
    assert _organization_type_from_notice("公告正文", "华为技术有限公司") == "COMPANY"
    assert _organization_type_from_notice("公告正文", "清华大学") == "UNIVERSITY"
    assert _organization_type_from_notice("公告正文", "中科院某研究院") == "RESEARCH_INSTITUTE"
    assert _organization_type_from_notice("公告正文", "某某人民医院") == "HOSPITAL"
    assert _organization_type_from_notice("某县人民政府 采购公告", "某单位") == "GOVERNMENT"
    assert _organization_type_from_notice("普通公告", "某某机构") == "UNKNOWN"


def test_awarded_supplier_company_gets_real_source_trace():
    """中标供应商入 Company 必须带可追溯来源 URL（任务书二十一）。"""
    with SessionLocal() as db:
        company, created = upsert_discovered_company(
            db, name="溯源测试股份有限公司", source_url="https://ccgp.example.com/notice/trace",
            organization_type="COMPANY",
        )
        db.commit()
        assert created
        assert company.discovery_source_url
        assert company.normalized_name == "溯源测试股份有限公司"
        row = db.scalar(select(Company).where(Company.id == company.id))
        assert row is not None
