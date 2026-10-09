"""T08.0 P0-1 回归：Source 与 Company 严格分离（Source Publisher ≠ Business Subject）。"""
from app.core.constants import is_source_platform_domain
from app.services import extractor
from app.services.extractor import FetchedPage


def test_platform_domain_blacklist():
    assert is_source_platform_domain("www.ccgp.gov.cn") is True
    assert is_source_platform_domain("ccgp.gov.cn") is True
    assert is_source_platform_domain("search.ccgp.gov.cn") is True
    assert is_source_platform_domain("www.zhaopin.com") is True
    assert is_source_platform_domain("www.gov.cn") is True
    # 业务企业域名不受影响
    assert is_source_platform_domain("www.hengfeng-test-example.com") is False
    assert is_source_platform_domain("shenzhou-digital.example.com") is False
    assert is_source_platform_domain(None) is False


def test_ccgp_page_never_identified_as_company():
    """ccgp 页面（og:site_name=中国政府采购网，无 JSON-LD）不得识别出平台主体。"""
    page = FetchedPage(
        url="http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t.htm",
        final_url="http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t.htm",
        status_code=200, content_type="text/html",
        title="清华大学67GHz矢量信号发生器中标公告_中国政府采购网",
        text="公告内容", html="<html></html>",
        og_site_name="中国政府采购网",
    )
    assert extractor.identify_company(page) is None


def test_business_site_still_identified():
    """正常企业官网识别不受平台黑名单影响（无 JSON-LD/og 时按域名 core 识别）。"""
    page = FetchedPage(
        url="https://www.hengfeng-test-example.com/news/1",
        final_url="https://www.hengfeng-test-example.com/news/1",
        status_code=200, content_type="text/html",
        title="恒锋智造 - 新闻中心", text="内容", html="<html></html>",
    )
    assert extractor.identify_company(page) == "hengfeng-test-example"


def test_ccgp_ingest_creates_no_platform_company(client, monkeypatch):
    """端到端：ccgp 页面 ingest 后 Company 列表不得新增 ccgp。"""
    from tests.test_url_ingest import MOCK_HTML
    from app.services import extractor

    ccgp_html = MOCK_HTML.replace("恒锋智造 - 新闻中心", "某大学仪器采购中标公告_中国政府采购网")
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: extractor.parse_html(
        url, url, 200, "text/html; charset=utf-8", ccgp_html))

    before = {c["company_name"] for c in client.get("/api/v1/companies", params={"page_size": 100}).json()["data"]["items"]}
    resp = client.post("/api/v1/ingest/url", json={"url": "http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t.htm"})
    assert resp.status_code == 200, resp.text
    after = {c["company_name"] for c in client.get("/api/v1/companies", params={"page_size": 100}).json()["data"]["items"]}
    assert "ccgp" not in after
    # 不得因为该页面新增平台公司（业务主体应由采购单位/供应商结构化提取）
    new_names = after - before
    assert all("ccgp" not in n.lower() and "政府采购" not in n for n in new_names), new_names
