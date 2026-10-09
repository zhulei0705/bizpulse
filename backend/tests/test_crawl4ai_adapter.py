"""T10-C1 隔离库/离线安全契约测试；模拟正文不计入真实 A/B 样本。"""
from types import SimpleNamespace
import json
import socket
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, func
from app.collectors import get_adapter, available_collectors
from app.collectors.base import CollectedItem
from app.collectors.crawl4ai_adapter import Crawl4AIAdapter, extract_dom, verify_quote
from app.collectors.crawl_policy import SafeFetch, Response, CrawlStopped, check_url, public_addresses, digest
from app.collectors.crawl_fields import extract_fields, strict_value

HTML = '<html><title>真实正文测试（离线夹具）</title><body><nav>首页 导航</nav><article>采购人：某某大学。预算为10万元。招聘工程师。</article></body></html>'
RULE = dict(status="ALLOWED", terms_url="https://example.com/terms", permission_url="https://example.com/terms",
            permission_quote="测试夹具明确允许采集", reviewed_by="pytest-fixture", reviewed_at="2026-10-08T00:00:00+00:00",
            expires_at="2099-01-01T00:00:00+00:00")
RULE["allowed_path_prefixes"] = ["/news"]

@pytest.fixture
def enabled(monkeypatch, tmp_path):
    path = tmp_path / "permission.json"
    path.write_text(json.dumps({"example.com": RULE}), encoding="utf-8")
    monkeypatch.setenv("CRAWL4AI_ENABLED", "true")
    monkeypatch.setenv("CRAWL4AI_PERMISSION_FILE", str(path))
    import app.collectors.crawl4ai_adapter as module
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(SafeFetch, "get", lambda self,url: Response(url,url,200,"text/html",HTML.encode(),{}))
    return module

def adapter(config=None):
    return Crawl4AIAdapter(SimpleNamespace(id="test",base_url="https://example.com/news"), config or {})

def test_optional_registry_default_off(monkeypatch):
    assert {"web_page", "rss", "manual_url", "crawl4ai"}.issubset(available_collectors())
    monkeypatch.delenv("CRAWL4AI_ENABLED", raising=False)
    with pytest.raises(ValueError, match="默认关闭"):
        get_adapter("crawl4ai", SimpleNamespace(base_url="https://example.com"))

def test_permission_cannot_be_self_approved(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL4AI_ENABLED", "true")
    monkeypatch.setenv("CRAWL4AI_PERMISSION_FILE", str(tmp_path/"absent"))
    with pytest.raises(CrawlStopped, match="SITE_PERMISSION"):
        adapter({"permission_allowed": True}).validate_config()

@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/", "https://example.com:8080/", "https://user:password@example.com/", "https://example.com/?token=secret", "https://example.com\\@localhost/"])
def test_unsafe_url(url):
    with pytest.raises(CrawlStopped):
        check_url(url, {"example.com"})

def test_mixed_dns_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a,**k: [(0,0,0,"",("8.8.8.8",443)),(0,0,0,"",("10.0.0.2",443))])
    with pytest.raises(CrawlStopped, match="NON_PUBLIC_DNS"):
        public_addresses("example.com",443)

def test_dns_rebinding_stops_before_connect(monkeypatch):
    import app.collectors.crawl_policy as policy
    client = SafeFetch({"example.com"})
    client.pins["example.com"] = frozenset({"8.8.8.8"})
    monkeypatch.setattr(policy,"public_addresses",lambda *a:frozenset({"1.1.1.1"}))
    monkeypatch.setattr(socket,"create_connection",lambda *a,**k:pytest.fail("不能连接变化的 DNS"))
    with pytest.raises(CrawlStopped,match="DNS_CHANGED"):
        client._one("https://example.com/")

def test_redirect_private_stops(monkeypatch):
    client = SafeFetch({"example.com"})
    monkeypatch.setattr(client,"_one",lambda url:Response(url,url,404,"text/plain",b"",{}) if url.endswith("robots.txt") else Response(url,url,302,"text/html",b"",{"location":"http://127.0.0.1/secret"}))
    with pytest.raises(CrawlStopped,match="DOMAIN_OR_PORT"):
        client.get("https://example.com/news")

def test_robots_denied(monkeypatch):
    client = SafeFetch({"example.com"})
    monkeypatch.setattr(client,"_one",lambda url:Response(url,url,200,"text/plain",b"User-agent: *\nDisallow: /",{}))
    with pytest.raises(CrawlStopped,match="ROBOTS_DENIED"):
        client.get("https://example.com/news")

def test_robots_failure_does_not_allow(monkeypatch):
    client = SafeFetch({"example.com"})
    monkeypatch.setattr(client,"_one",lambda url:Response(url,url,500,"text/plain",b"",{}))
    with pytest.raises(CrawlStopped,match="ROBOTS_UNVERIFIED"):
        client.get("https://example.com/news")

def test_static_never_launches_browser(enabled, monkeypatch):
    monkeypatch.setattr(enabled,"render_guarded",lambda *a,**k:pytest.fail("静态 URL 不应启动浏览器"))
    item = adapter({"css_selector":"article"}).fetch()[0]
    assert item.raw_text == "采购人：某某大学。预算为10万元。招聘工程师。"
    assert item.extra["structured_fields"]["deadline"]["status"] == "UNKNOWN"
    assert item.extra["robots_checked"]
    assert Path(enabled.BASE_DIR/item.extra["raw_bytes_path"]).read_bytes() == HTML.encode()
    assert "首页" in Path(enabled.BASE_DIR/item.extra["raw_text_path"]).read_text(encoding="utf-8")
    assert "首页" not in item.raw_text

def test_js_requires_actual_diagnosis(enabled):
    with pytest.raises(ValueError,match="诊断"):
        adapter({"mode":"js"}).validate_config()
    with pytest.raises(CrawlStopped,match="JS_DIAGNOSIS"):
        adapter({"mode":"js","js_diagnosis":{"marker":"absent", "reason":"测试", "http_failure":"PARSE_EMPTY"}}).fetch()

def test_js_extract_and_evidence_hash(enabled,monkeypatch):
    monkeypatch.setattr(enabled,"render_guarded",lambda *a,**k:{"html":HTML.replace("10万元","20万元")})
    item = adapter({"mode":"js","css_selector":"article","js_diagnosis":{"marker":"article","reason":"离线 JS 夹具","http_failure":"JS_RENDER_REQUIRED"}}).fetch()[0]
    quote = "20万元"
    start = item.raw_text.index(quote)
    assert verify_quote(item,quote,start,start+len(quote),item.extra["cleaned_text_hash"])
    assert not verify_quote(item,"10万元",start,start+len(quote),item.extra["cleaned_text_hash"])
    assert not verify_quote(item,quote,start,start+len(quote),digest("其他版本"))
    assert item.extra["rendered_html_path"]

def test_render_failure_only_safe_fallback(enabled,monkeypatch):
    def fail(*a,**k): raise CrawlStopped("SDK_RENDER_FAILED")
    monkeypatch.setattr(enabled,"render_guarded",fail)
    item = adapter({"mode":"js","css_selector":"article","js_diagnosis":{"marker":"article","reason":"诊断","http_failure":"PARSE_EMPTY"}}).fetch()[0]
    assert item.extra["render_status"]["fallback"] == "SAFE_HTTP_BODY"
    def unsafe(*a,**k): raise CrawlStopped("UNSAFE_BROWSER_TARGET")
    monkeypatch.setattr(enabled,"render_guarded",unsafe)
    with pytest.raises(CrawlStopped,match="UNSAFE_BROWSER_TARGET"):
        adapter({"mode":"js","js_diagnosis":{"marker":"article","reason":"诊断","http_failure":"PARSE_EMPTY"}}).fetch()

@pytest.mark.parametrize("extra",[{"js_code":"evil()"},{"cookies":[]},{"headers":{"Authorization":"secret"}},{"extra_args":["--no-sandbox"]},{"pdf_strategy":"default"}])
def test_no_injection_config(enabled,extra):
    with pytest.raises(ValueError,match="禁止"):
        adapter(extra).validate_config()

def test_pdf_no_placeholder(enabled,monkeypatch):
    monkeypatch.setattr(SafeFetch,"get",lambda self,url:Response(url,url,200,"application/pdf",b"%PDF-fake",{}))
    with pytest.raises(CrawlStopped,match="PDF_STRATEGY_NOT_CONFIGURED"):
        adapter().fetch()

def test_access_barrier_stops(enabled,monkeypatch):
    monkeypatch.setattr(SafeFetch,"get",lambda self,url:Response(url,url,200,"text/html",b'<input type="password">',{}))
    with pytest.raises(CrawlStopped,match="ACCESS_BARRIER"):
        adapter().fetch()

@pytest.mark.parametrize("field,value",[("deadline","2026-02-30"),("deadline","明天"),("budget","100"),("budget","-10万元"),("buyer","某某供应商公司"),("buyer","供应商：某某公司"),("supplier","采购人：某某大学")])
def test_strict_fields_unknown(field,value):
    assert strict_value(field,value) is None

def test_strict_fields_with_snapshot():
    fields = extract_fields('<p id="buyer">采购人：某某大学</p><p id="budget">10.50万元</p><p id="date">2026年10月08日</p>',{"buyer":"#buyer","budget":"#budget","published_at":"#date"})
    assert fields["buyer"]["value"] == "某某大学"
    assert fields["budget"]["value"] == "105000.00"
    assert fields["deadline"]["status"] == "UNKNOWN"
    assert fields["published_at"]["timezone"] == "UNKNOWN"

def test_versioning_and_no_business_auto_creation(enabled, monkeypatch):
    from app.db.session import SessionLocal
    from app.models.source import Source, SourceRecord
    from app.models.signal import Signal
    from app.models.company import Company
    from app.services.collection_engine import persist_collected
    with SessionLocal() as db:
        source = Source(name="C1离线夹具"+uuid.uuid4().hex,source_type="OFFICIAL_WEBSITE",collector_type="crawl4ai",reliability_grade="C")
        db.add(source); db.flush()
        companies = db.scalar(select(func.count()).select_from(Company))
        signals = db.scalar(select(func.count()).select_from(Signal))
        item = adapter({"css_selector":"article"}).fetch()[0]
        record, outcome = persist_collected(db,source,item)
        assert outcome == "CREATED" and record.company_id is None and record.verification_status == "UNVERIFIED"
        same,outcome = persist_collected(db,source,item)
        assert outcome == "SKIPPED_UNCHANGED" and same.id == record.id
        monkeypatch.setattr(SafeFetch,"get",lambda self,url:Response(url,url,200,"text/html",HTML.replace("10万元","20万元").encode(),{}))
        item = adapter({"css_selector":"article"}).fetch()[0]
        version,outcome = persist_collected(db,source,item)
        assert outcome == "UPDATED_VERSION" and version.parent_record_id == record.id and version.version_number == 2
        assert not record.is_latest and record.raw_text != version.raw_text
        assert db.scalar(select(func.count()).select_from(Company)) == companies
        assert db.scalar(select(func.count()).select_from(Signal)) == signals
        db.rollback()

def test_evidence_mismatch_blocks_before_write(enabled):
    from app.db.session import SessionLocal
    from app.models.source import Source, SourceRecord
    from app.services.collection_engine import persist_collected
    with SessionLocal() as db:
        source = Source(name="快照错误夹具",source_type="OFFICIAL_WEBSITE",collector_type="crawl4ai")
        db.add(source); db.flush()
        item = adapter({"css_selector":"article"}).fetch()[0]
        item.raw_text += "不存在的事实"
        before = db.scalar(select(func.count()).select_from(SourceRecord))
        with pytest.raises(CrawlStopped,match="EVIDENCE_SNAPSHOT_MISMATCH"):
            persist_collected(db,source,item)
        assert db.scalar(select(func.count()).select_from(SourceRecord)) == before
        db.rollback()

@pytest.mark.parametrize("mode,reason",[("size","BODY_SIZE_LIMIT"),("stream","BODY_RESOURCE_LIMIT"),("denied","ACCESS_DENIED_STOP"),("peer","PEER_IP_MISMATCH")])
def test_pinned_transport_resource_caps(monkeypatch,mode,reason):
    import app.collectors.crawl_policy as policy
    class Sock:
        def getpeername(self): return ("10.0.0.1" if mode=="peer" else "8.8.8.8",443)
        def close(self): pass
    class Reply:
        status=403 if mode=="denied" else 200
        def getheaders(self): return [("content-type","text/html"),("content-length","2000001" if mode=="size" else "1")]
        def read(self,*a):
            if mode=="stream": return b"x"*65536
            return b""
    class Conn:
        def __init__(self,*a,**k): pass
        def request(self,*a,**k): pass
        def getresponse(self): return Reply()
        def close(self): pass
    monkeypatch.setattr(policy,"public_addresses",lambda *a:frozenset({"8.8.8.8"}))
    monkeypatch.setattr(policy.http.client,"HTTPConnection",Conn)
    monkeypatch.setattr(socket,"create_connection",lambda address,**kwargs:Sock() if address[0]=="8.8.8.8" else pytest.fail("必须连接已固定IP"))
    monkeypatch.setattr(policy.ssl,"create_default_context",lambda:SimpleNamespace(wrap_socket=lambda sock,server_hostname:sock))
    with pytest.raises(CrawlStopped,match=reason):
        SafeFetch({"example.com"},max_bytes=100000)._one("https://example.com/test")

def test_real_sdk_inline_js_offline():
    # 真 SDK/Chromium、离线夹具；所有页面响应由桥接注入，没有站点访问。
    from app.collectors.crawl4ai_adapter import render_guarded
    html='<html><title>JS离线夹具</title><body><article id="body"></article><script>document.querySelector("article").textContent="JS生成正文。这是用于验证确定性DOM提取和离线网络阻断的测试夹具，页面文字由内联脚本生成，测试不访问实际站点，也不产生商业信号和采购事实。正文必须来自渲染后的DOM快照，且可以通过精确字符偏移回溯。";</script></body></html>'
    result=render_guarded("https://example.com/fixture",html,SafeFetch({"example.com"}),wait_ms=100)
    assert "JS生成正文" in extract_dom(result["html"],"https://example.com","article")[2]
    assert result["requests"] == 0

def test_real_sdk_private_request_stops_offline():
    from app.collectors.crawl4ai_adapter import render_guarded
    html='<html><body><script>fetch("http://127.0.0.1/secret").catch(()=>{});</script></body></html>'
    with pytest.raises(CrawlStopped,match="UNSAFE_BROWSER_TARGET"):
        render_guarded("https://example.com/fixture",html,SafeFetch({"example.com"}),wait_ms=300)

def test_crlf_response_preserves_bytes_and_evidence(enabled,monkeypatch):
    from app.collectors.crawl4ai_adapter import validate_crawl_evidence
    original=HTML.replace("<article>","\r\n<article>").encode()
    monkeypatch.setattr(SafeFetch,"get",lambda self,url:Response(url,url,200,"text/html",original,{}))
    item=adapter({"css_selector":"article"}).fetch()[0]
    validate_crawl_evidence(item)
    assert (enabled.BASE_DIR/item.extra["raw_bytes_path"]).read_bytes()==original
    assert "NORMALIZED_NEWLINES" in item.extra["html_representation"]
