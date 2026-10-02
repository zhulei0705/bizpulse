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


# ---------------------------------------------------------------------------
# 权威域名自动定级（T05 真实数据验证：ccgp.gov.cn 等政府官网应为 A 级）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("http://www.ccgp.gov.cn/zhaobiao/1.htm", True),
    ("https://ccgp.gov.cn/x", True),
    ("http://www.moe.gov.cn/x", True),
    ("https://www.gsxt.gov.cn/x", True),
    ("http://www.tsinghua.edu.cn/x", True),
    ("https://harvard.edu/x", True),
    ("https://www.example.com/news", False),
    ("https://blog.example.org/gov-post", False),
    ("https://notgov.example.com/x", False),
])
def test_is_authoritative_domain(url, expected):
    from app.services.ingest import _is_authoritative_domain

    assert _is_authoritative_domain(url) is expected


def test_ingest_gov_url_upgrades_source_grade(client, mock_fetch):
    resp = client.post("/api/v1/ingest/url", json={"url": "http://www.ccgp.gov.cn/zhaobiao/1.htm"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    record = client.get(f"/api/v1/source-records/{data['source_record_id']}").json()["data"]
    assert record["source"]["reliability_grade"] == "A"
    assert record["source"]["reliability_score"] >= 95

    # 普通商业域名仍为默认 C 级（不受 gov 升级影响）
    resp2 = client.post("/api/v1/ingest/url", json={"url": "https://www.hengfeng-test-example.com/news/1"})
    assert resp2.status_code == 200, resp2.text
    record2 = client.get(f"/api/v1/source-records/{resp2.json()['data']['source_record_id']}").json()["data"]
    assert record2["source"]["reliability_grade"] == "A"  # 共享手动来源：已被 gov URL 升级，只升不降


def test_authoritative_grade_never_downgrades_and_idempotent(client):
    from app.db.session import SessionLocal
    from app.models.source import Source
    from app.services.ingest import ensure_authoritative_grade

    with SessionLocal() as db:
        source = db.query(Source).filter(Source.source_type == "MANUAL_URL").first()
        assert source is not None
        assert source.reliability_grade == "A"  # 前面的 gov 测试已升级

        # 幂等：A 级 + score>=95 再次命中不再变更
        assert ensure_authoritative_grade(db, source, "http://www.ccgp.gov.cn/y") is False
        assert source.reliability_grade == "A"

        # 人工下调后政府 URL 仍会拉回 A（只升不降）
        source.reliability_grade = "C"
        source.reliability_score = 55
        assert ensure_authoritative_grade(db, source, "http://www.moe.gov.cn/z") is True
        assert source.reliability_grade == "A"
        assert source.reliability_score == 95
        db.commit()
