"""T08 企业发现测试：官网站内发现（同域限制/分类/上限）、中标供应商提取、Company Gate。"""
import uuid

from app.services.company_discovery import (
    classify_link,
    extract_awarded_suppliers,
    discover_website_sections,
    upsert_discovered_company,
)

MOCK_HOME = """
<html><head><title>恒锋智造 - 官网</title></head><body>
<nav>
  <a href="/news">新闻中心</a>
  <a href="/careers">加入我们</a>
  <a href="/contact">联系我们</a>
  <a href="/products">产品中心</a>
  <a href="/solutions">解决方案</a>
  <a href="/about">公司简介</a>
  <a href="https://external-site.com/x">外链</a>
  <a href="javascript:void(0)">无效</a>
</nav>
</body></html>
"""


def _mock_fetch(monkeypatch, html=MOCK_HOME):
    from app.services import extractor
    from app.services.extractor import parse_html

    def _fake(url):
        return parse_html(url, url, 200, "text/html; charset=utf-8", html)
    monkeypatch.setattr(extractor, "fetch_public_page", _fake)


def test_classify_link_dimensions():
    assert classify_link("https://x.com/news", "新闻中心") == "NEWS"
    assert classify_link("https://x.com/careers", "加入我们") == "CAREERS"
    assert classify_link("https://x.com/contact", "联系我们") == "CONTACT"
    assert classify_link("https://x.com/products", "产品中心") == "PRODUCTS"
    assert classify_link("https://x.com/page1", "无关页面") is None


def test_website_discovery_same_domain_only(monkeypatch):
    _mock_fetch(monkeypatch)
    result = discover_website_sections("https://www.hengfeng-test-example.com")
    dims = {p.dimension for p in result.pages}
    assert {"NEWS", "CAREERS", "CONTACT", "PRODUCTS", "SOLUTIONS", "ABOUT"} <= dims
    # 外链不被收录（限同域名）
    assert all(p.url.startswith("https://www.hengfeng-test-example.com") for p in result.pages)
    assert len(result.pages) <= 30


def test_extract_awarded_suppliers_real_patterns():
    text = """
    一、项目编号：GC-HX2601
    二、项目名称：实验室仪器采购项目
    中标供应商名称：北京华谱科仪科技有限公司
    中标金额：￥1,280,000
    三、中标供应商：上海精密仪器股份有限公司
    采购人：某大学
    四、成交供应商：深圳市恒泰检测设备有限公司
    """
    suppliers = extract_awarded_suppliers(text)
    names = [s["name"] for s in suppliers]
    assert "北京华谱科仪科技有限公司" in names
    assert "上海精密仪器股份有限公司" in names
    assert "深圳市恒泰检测设备有限公司" in names
    # 采购人不是供应商（正则不含"采购人"模式）
    assert all("某大学" != n for n in names)


def test_extract_suppliers_empty_when_no_match():
    assert extract_awarded_suppliers("这是招标公告，尚未开标。") == []
    assert extract_awarded_suppliers(None) == []


def test_upsert_company_requires_source(db_session=None):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        from app.db.session import SessionLocal
        with SessionLocal() as db:
            import pytest
            with pytest.raises(ValueError):
                upsert_discovered_company(db, name="无来源企业", source_url="")


def test_upsert_company_gate_and_dedup():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import SessionLocal
    from app.models.company import Company

    suffix = uuid.uuid4().hex[:6]
    with TestClient(app):
        with SessionLocal() as db:
            company, created = upsert_discovered_company(
                db, name=f"华谱科仪{suffix}有限公司", source_url="https://ccgp.gov.cn/notice/1.htm",
                organization_type="COMPANY",
            )
            db.commit()
            assert created is True
            assert company.verification_status == "PUBLIC_SOURCE_VERIFIED"
            assert company.organization_type == "COMPANY"
            assert company.discovery_source_url == "https://ccgp.gov.cn/notice/1.htm"

            # 重复发现（同 normalized_name）→ 不新建
            again, created2 = upsert_discovered_company(
                db, name=f"华谱科仪{suffix}有限公司", source_url="https://ccgp.gov.cn/notice/2.htm",
            )
            db.commit()
            assert created2 is False
            assert again.id == company.id