"""手动 URL 分析测试：SSRF 防护、抓取解析（Mock HTTP）、数据链、内容去重。

pytest 不访问公网：所有 HTTP 抓取均被 Mock。
"""
import pytest

from app.services import extractor
from app.services.extractor import FetchedPage, URLSafetyError, validate_public_url

MOCK_HTML = """
<html>
  <head>
    <title>恒锋智造 - 新闻中心</title>
    <meta property="og:site_name" content="恒锋智造"/>
    <meta name="description" content="恒锋智造是一家精密制造企业"/>
    <script type="application/ld+json">{"@type":"Organization","name":"恒锋智造股份有限公司"}</script>
  </head>
  <body>
    <nav>导航 导航 首页 产品 关于我们</nav>
    <article>
      <h1>公司动态</h1>
      <p>恒锋智造宣布完成A轮融资5000万元，用于海外扩张与产能扩建。</p>
      <p>同时公司正在招聘海外销售经理5名、算法工程师2名。</p>
      <p>销售部门仍依赖人工录入报表和重复劳动，处理效率低下。</p>
      <footer>版权所有 备案号</footer>
    </article>
  </body>
</html>
"""


def _mock_page(url: str = "https://www.hengfeng-test-example.com/news/1") -> FetchedPage:
    parsed = extractor.parse_html(url, url, 200, "text/html; charset=utf-8", MOCK_HTML)
    return parsed


@pytest.fixture()
def mock_fetch(monkeypatch):
    calls: list[str] = []

    def _fake_fetch(url: str) -> FetchedPage:
        calls.append(url)
        return _mock_page(url)

    monkeypatch.setattr(extractor, "fetch_public_page", _fake_fetch)
    return calls


# ---------------------------------------------------------------------------
# SSRF / URL 安全校验
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_url", [
    "http://localhost/news",
    "http://localhost:8080/",
    "https://sub.localhost/x",
    "ftp://files.example.com/doc",
    "file:///C:/Windows/system.ini",
    "http://127.0.0.1:8000/api",
    "http://10.1.2.3/inner",
    "http://172.16.0.9/inner",
    "http://192.168.1.10/router",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/x",
    "http://0.0.0.0/x",
])
def test_validate_public_url_blocks_private_and_non_http(bad_url):
    with pytest.raises(URLSafetyError):
        validate_public_url(bad_url)


def test_validate_public_url_accepts_public(monkeypatch):
    class _Info:
        def __init__(self, ip): self._ip = ip

    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))])
    assert validate_public_url("https://www.example.com/news") == "https://www.example.com/news"


def test_validate_public_url_rejects_unresolvable(monkeypatch):
    import socket

    def _fail(host, port):
        raise OSError("no dns")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    with pytest.raises(URLSafetyError):
        validate_public_url("https://no-such-host-invalid.example.com/")


# ---------------------------------------------------------------------------
# 正文解析
# ---------------------------------------------------------------------------

def test_parse_html_extracts_content_and_drops_noise():
    page = _mock_page()
    assert page.title == "恒锋智造 - 新闻中心"
    assert page.og_site_name == "恒锋智造"
    assert page.organization == "恒锋智造股份有限公司"
    assert "导航" not in page.text
    assert "版权所有" not in page.text
    assert "完成A轮融资" in page.text
    assert "招聘海外销售经理" in page.text


# ---------------------------------------------------------------------------
# 企业识别
# ---------------------------------------------------------------------------

def test_identify_company_prefers_jsonld_then_og_then_domain():
    page = _mock_page()
    assert extractor.identify_company(page) == "恒锋智造股份有限公司"

    page.organization = None
    assert extractor.identify_company(page) == "恒锋智造"

    page.og_site_name = None
    assert extractor.identify_company(page) == "hengfeng-test-example"


# ---------------------------------------------------------------------------
# 规则信号提取
# ---------------------------------------------------------------------------

def test_rule_extractor_finds_specific_signals():
    page = _mock_page()
    hits = {hit.signal_type for hit in extractor.extract_signal_hits(page)}
    assert "SALES_HIRING" in hits
    assert "AI_HIRING" in hits
    assert "FUNDING" in hits
    assert "OVERSEAS_EXPANSION" in hits
    # 泛化 HIRING 被更具体类型覆盖时不重复输出
    if {"SALES_HIRING", "AI_HIRING"} & hits:
        assert "HIRING" not in hits


# ---------------------------------------------------------------------------
# 端到端（Mock HTTP）：URL → SourceRecord → Company → Signal
# ---------------------------------------------------------------------------

def test_ingest_url_builds_traceable_chain(client, mock_fetch):
    resp = client.post("/api/v1/ingest/url", json={"url": "https://www.hengfeng-test-example.com/news/1", "note": "验收测试"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["company_id"]
    assert len(data["signal_ids"]) >= 2
    assert data["llm_configured"] is False

    # SourceRecord 可查、URL 可追溯
    record = client.get(f"/api/v1/source-records/{data['source_record_id']}").json()["data"]
    assert record["url"] == "https://www.hengfeng-test-example.com/news/1"
    assert record["source"]["reliability_grade"] == "C"

    # Company 自动创建
    company = client.get(f"/api/v1/companies/{data['company_id']}").json()["data"]
    assert "恒锋智造" in company["company_name"]
    assert company["domain"] == "www.hengfeng-test-example.com"

    # Signal 关联证据
    signals = client.get("/api/v1/signals", params={"company_id": data["company_id"]}).json()["data"]["items"]
    assert len(signals) >= 2
    assert all(s["evidence"]["source_record_id"] == data["source_record_id"] for s in signals)
    assert all(s["fact_or_inference"] == "FACT" for s in signals)


def test_ingest_url_deduplicates_content(client, mock_fetch):
    url = "https://www.hengfeng-test-example.com/news/1"
    first = client.post("/api/v1/ingest/url", json={"url": url}).json()["data"]
    second = client.post("/api/v1/ingest/url", json={"url": url}).json()
    assert second["message"] == "duplicate_record_reused"
    assert second["data"]["duplicate"] is True
    assert second["data"]["source_record_id"] == first["source_record_id"]


def test_ingest_url_rejects_private_targets(client):
    resp = client.post("/api/v1/ingest/url", json={"url": "http://192.168.1.1/admin"})
    assert resp.status_code == 422
    assert "禁止" in resp.json()["detail"]


def test_ingest_url_unreachable_returns_502(client, monkeypatch):
    def _fail(url: str) -> FetchedPage:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(extractor, "fetch_public_page", _fail)
    resp = client.post("/api/v1/ingest/url", json={"url": "https://valid-public-example.com/x"})
    assert resp.status_code == 502


def test_ingest_failure_does_not_break_system(client, mock_fetch):
    # 采集失败前后系统均可正常服务
    assert client.get("/api/v1/health").status_code == 200
    client.post("/api/v1/ingest/url", json={"url": "http://localhost/x"})
    assert client.get("/api/v1/health").json()["data"]["status"] == "ok"
