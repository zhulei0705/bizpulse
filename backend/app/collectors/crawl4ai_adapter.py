"""可选 SDK 适配器。只生成未核实 SourceRecord；许可由服务器文件提供。"""
from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.collectors.base import CollectedItem, CollectorAdapter
from app.collectors.crawl_policy import SafeFetch, CrawlStopped, check_url, digest
from app.collectors.crawl_fields import extract_fields, FIELDS
from app.core.config import BASE_DIR
from app.services.extractor import parse_html

PARSER_VERSION = "bizpulse-crawl4ai-0.9.4-css-v2"
_BROWSER_SLOT = threading.BoundedSemaphore(1)


def site_permission(host: str) -> dict:
    # Source.config_json 不能自行声明采集合法；只能引用管理员维护的站点许可。
    path = Path(os.environ.get("CRAWL4AI_PERMISSION_FILE", str(BASE_DIR / "data/crawl_permissions.json")))
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
        rule = rules[host]
        expires = datetime.fromisoformat(rule["expires_at"])
        if not expires.tzinfo:
            raise ValueError
        if rule["status"] != "ALLOWED" or not all(rule.get(k) for k in (
            "terms_url", "permission_url", "permission_quote", "reviewed_by", "reviewed_at")):
            raise ValueError
        if expires <= datetime.now(timezone.utc):
            raise ValueError
        prefixes = rule.get("allowed_path_prefixes")
        if not isinstance(prefixes, list) or not prefixes or not all(isinstance(p, str) and p.startswith("/") for p in prefixes):
            raise ValueError
        check_url(rule["terms_url"], {urlsplit(rule["terms_url"]).hostname or ""})
        return rule
    except (OSError, ValueError, KeyError, TypeError):
        raise CrawlStopped("SITE_PERMISSION_UNVERIFIED") from None


def extract_dom(html: str, url: str, selector: str | None = None, *, legacy: bool = False) -> tuple[str, str | None, str]:
    """原始可见文本与清洗正文分别保存；Evidence 对应清洗正文 Unicode 字符偏移。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    raw = soup.get_text(" ", strip=True)
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    if selector:
        # raw 已取自未经正文清洗的 DOM；后续操作只改变清洗副本。
        for tag in ([] if legacy else soup(['nav', 'footer', 'aside', 'form', 'svg', 'iframe'])):
            tag.decompose()
        for tag in ([] if legacy else soup.find_all(attrs={'aria-hidden': 'true'})):
            tag.decompose()
        nodes = soup.select(selector)
        cleaned = "\n".join(node.get_text(" ", strip=True) for node in nodes)
    else:
        cleaned = parse_html(url, url, 200, "text/html", html).text
    if len(cleaned) > 200_000 or len(raw) > 500_000:
        raise CrawlStopped("TEXT_RESOURCE_LIMIT")
    return raw, title, cleaned


def verify_quote(item: CollectedItem, quote: str, start: int, end: int, text_hash: str) -> bool:
    text = item.raw_text or ""
    return bool(quote and isinstance(start, int) and isinstance(end, int)
                and 0 <= start < end <= len(text) and text[start:end] == quote
                and digest(text) == text_hash)


def validate_crawl_evidence(item: CollectedItem) -> None:
    """入库前再验证快照与正文；失败发生在任何业务写入之前。"""
    try:
        meta = item.extra
        root = (BASE_DIR / "data/raw/crawl4ai").resolve()
        def snapshot(key):
            path = (BASE_DIR / meta[key]).resolve()
            if not path.is_relative_to(root) or path.stat().st_size > 5_000_000:
                raise ValueError
            return path
        cleaned = snapshot("cleaned_text_path").read_text(encoding="utf-8")
        original = snapshot("raw_html_path").read_text(encoding="utf-8")
        binary = snapshot("raw_bytes_path").read_bytes()
        if cleaned != item.raw_text or digest(cleaned) != meta["cleaned_text_hash"]:
            raise ValueError
        if digest(original) != meta["raw_html_hash"] or digest(binary) != meta["raw_bytes_hash"]:
            raise ValueError
        basis = original
        if meta.get("rendered_html_path"):
            basis = snapshot("rendered_html_path").read_text(encoding="utf-8")
            if digest(basis) != meta["rendered_html_hash"]:
                raise ValueError
        version = meta.get('parser_version')
        if version not in {PARSER_VERSION, 'bizpulse-crawl4ai-0.9.4-css-v1'}:raise ValueError
        if extract_dom(basis, item.canonical_url, meta.get("css_selector"), legacy=version.endswith('css-v1'))[2] != cleaned:
            raise ValueError
    except (OSError, KeyError, ValueError, TypeError):
        raise CrawlStopped("EVIDENCE_SNAPSHOT_MISMATCH") from None


def render_guarded(url: str, html: str, client: SafeFetch, *, wait_ms=800) -> dict:
    """独立短生命周期子进程运行 SDK，监视整个进程树；无新增服务。"""
    import psutil
    if importlib.metadata.version("crawl4ai") != "0.9.4":
        raise CrawlStopped("SDK_VERSION_MISMATCH")
    if not _BROWSER_SLOT.acquire(blocking=False):
        raise CrawlStopped("BROWSER_CONCURRENCY_LIMIT")
    started = time.monotonic()
    proc = None
    known = []
    peak = 0
    try:
        with tempfile.TemporaryDirectory(prefix="c1-", dir=str(BASE_DIR / "data")) as tmp:
            directory = Path(tmp)
            payload = dict(url=url, html=html, domains=sorted(client.domains),
                           pins={k: sorted(v) for k, v in client.pins.items()},
                           wait_ms=min(int(wait_ms), 3000), interval=client.interval,
                           bytes_used=client.bytes, requests_used=client.requests)
            payload["allowed_paths"] = client.allowed_paths
            (directory / "input.json").write_text(json.dumps(payload), encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k.upper() in {
                "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "LOCALAPPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"}}
            env.update(PYTHONIOENCODING="utf-8", PLAYWRIGHT_BROWSERS_PATH=str(BASE_DIR / ".browsers"),
                       CRAWL4_AI_BASE_DIRECTORY=str(BASE_DIR / "data/crawl4ai_cache"))
            with (directory / "worker.log").open("w", encoding="utf-8") as log:
                proc = subprocess.Popen([sys.executable, "-m", "app.collectors.crawl4ai_worker", str(directory)],
                                        cwd=BASE_DIR, env=env, stdout=log, stderr=log,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                parent = psutil.Process(proc.pid)
                while proc.poll() is None:
                    try:
                        known = [parent, *parent.children(recursive=True)]
                        memory = sum(p.memory_info().rss for p in known if p.is_running())
                        cpu = sum(sum(p.cpu_times()[:2]) for p in known if p.is_running())
                        peak = max(peak, memory)
                    except psutil.Error:
                        memory = cpu = 0
                    if time.monotonic() - started > 50 or memory > 800 * 1024**2 or cpu > 35:
                        raise CrawlStopped("BROWSER_RESOURCE_LIMIT")
                    time.sleep(0.05)
            output = directory / "output.json"
            if proc.returncode or not output.exists() or output.stat().st_size > 5_000_000:
                raise CrawlStopped("SDK_RENDER_FAILED")
            result = json.loads(output.read_text(encoding="utf-8"))
            if result.get("stop"):
                raise CrawlStopped(result["stop"])
            result.update(peak_rss_bytes=peak, elapsed_seconds=round(time.monotonic()-started, 3))
            return result
    finally:
        # 包括 SDK 异常留下的 Chromium：退出后也清理已观察到的子进程。
        for child in reversed(known):
            try:
                if child.is_running():
                    child.kill()
            except psutil.Error:
                pass
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        _BROWSER_SLOT.release()


class Crawl4AIAdapter(CollectorAdapter):
    collector_type = "crawl4ai"

    def validate_config(self) -> None:
        if os.environ.get("CRAWL4AI_ENABLED", "false").lower() != "true":
            raise ValueError("Crawl4AI 默认关闭；须配置服务器 CRAWL4AI_ENABLED=true")
        url = self.config.get("url") or self.source.base_url or ""
        host = urlsplit(url).hostname or ""
        check_url(url, {host})
        self.permission = site_permission(host)
        self.url = url
        if self.config.get("mode", "http") not in {"http", "js"}:
            raise ValueError("mode 必须为 http 或 js")
        if self.config.get("mode") == "js" and not self.config.get("js_diagnosis"):
            raise ValueError("启动浏览器前必须提供 JS 依赖诊断")
        forbidden = {"js_code", "hooks", "cookies", "headers", "proxy_config", "cdp_url", "extra_args",
                     "user_data_dir", "llm_config", "init_scripts", "pdf_strategy"}
        if forbidden.intersection(self.config):
            raise ValueError("禁止从 Source 配置注入可执行代码、凭证或浏览器内部参数")
        selector = self.config.get("css_selector")
        if selector:
            if not isinstance(selector, str) or len(selector) > 300:
                raise ValueError("CSS 选择器无效")
            try:
                BeautifulSoup("", "html.parser").select(selector)
            except Exception:
                raise ValueError("CSS 选择器无效") from None
        field_css = self.config.get("field_css", {})
        if not isinstance(field_css, dict) or set(field_css) - FIELDS:
            raise ValueError("field_css 含未知字段")
        for value in field_css.values():
            if not isinstance(value, str) or len(value) > 300:
                raise ValueError("字段选择器无效")
            try:
                BeautifulSoup("", "html.parser").select(value)
            except Exception:
                raise ValueError("字段选择器无效") from None

    def fetch(self) -> list[CollectedItem]:
        self.validate_config()
        started = time.monotonic()
        client = SafeFetch({urlsplit(self.url).hostname}, interval=self.permission.get("interval_seconds", 2),
                           allowed_paths=self.permission["allowed_path_prefixes"])
        try:
            response = client.get(self.url)
            if response.status != 200:
                raise CrawlStopped("HTTP_STATUS_FAILED")
            if "pdf" in response.content_type.lower() or response.body.startswith(b"%PDF"):
                # V1 无 PDF 解析策略，不调用 SDK 默认 PDF 下载器，不产生占位正文。
                raise CrawlStopped("PDF_STRATEGY_NOT_CONFIGURED")
            if not any(t in response.content_type.lower() for t in ("text/html", "application/xhtml+xml", "text/plain")):
                raise CrawlStopped("CONTENT_TYPE_NOT_ALLOWED")
            # 原始响应字节另存，解码快照统一换行，避免 Windows 文本 I/O 改写哈希基准。
            html = response.text().replace("\r\n", "\n").replace("\r", "\n")
            if re_access_barrier(html):
                raise CrawlStopped("ACCESS_BARRIER_STOP")
            raw, title, cleaned = extract_dom(html, response.final_url, self.config.get("css_selector"))
            original_cleaned = cleaned
            render = {}
            rendered_html = None
            if self.config.get("mode") == "js":
                # 诊断证据必须实际存在于收到的原始 HTML，而非单个启用开关。
                diagnosis = self.config["js_diagnosis"]
                if (not isinstance(diagnosis, dict) or not isinstance(diagnosis.get("marker"), str)
                    or not diagnosis["marker"] or diagnosis["marker"] not in html
                    or not diagnosis.get("reason") or diagnosis.get("http_failure") not in {"PARSE_EMPTY", "JS_RENDER_REQUIRED"}):
                    raise CrawlStopped("JS_DIAGNOSIS_UNVERIFIED")
                try:
                    render = render_guarded(response.final_url, html, client,
                                            wait_ms=self.config.get("wait_ms", 800))
                    rendered_html = render["html"]
                    _, title, cleaned = extract_dom(rendered_html, response.final_url, self.config.get("css_selector"))
                    if re_access_barrier(rendered_html):
                        raise CrawlStopped("ACCESS_BARRIER_STOP")
                except CrawlStopped as exc:
                    # 仅运行时故障可以退回已安全抓取的有效正文。任何安全异常停止。
                    if str(exc) != "SDK_RENDER_FAILED" or not original_cleaned:
                        raise
                    cleaned = original_cleaned
                    render = {"fallback_reason": "SDK_RENDER_FAILED", "fallback": "SAFE_HTTP_BODY"}
            if not cleaned.strip():
                raise CrawlStopped("PARSE_EMPTY")
            key = digest(response.body + cleaned.encode() + (rendered_html or "").encode())
            root = BASE_DIR / "data/raw/crawl4ai"
            root.mkdir(parents=True, exist_ok=True)
            binary_path = root / f"{key}.response.bin"
            if binary_path.exists() and binary_path.read_bytes() != response.body:
                raise CrawlStopped("EVIDENCE_SNAPSHOT_MISMATCH")
            if not binary_path.exists():
                binary_path.write_bytes(response.body)
            for suffix, value in (("html", html), ("raw.txt", raw), ("clean.txt", cleaned), ("rendered.html", rendered_html)):
                if value is not None:
                    path = root / f"{key}.{suffix}"
                    if path.exists() and path.read_text(encoding="utf-8") != value:
                        raise CrawlStopped("EVIDENCE_SNAPSHOT_MISMATCH")
                    if not path.exists():
                        path.write_text(value, encoding="utf-8", newline="")
            extra = dict(original_url=self.url, final_url=response.final_url,
                         source_domain=urlsplit(response.final_url).hostname,
                         captured_at=datetime.now(timezone.utc).isoformat(), parser_version=PARSER_VERSION,
                         raw_html_path=f"data/raw/crawl4ai/{key}.html", raw_text_path=f"data/raw/crawl4ai/{key}.raw.txt",
                         cleaned_text_path=f"data/raw/crawl4ai/{key}.clean.txt", cleaned_text_hash=digest(cleaned),
                         raw_html_hash=digest(html), raw_bytes_hash=digest(response.body),
                         raw_bytes_path=f"data/raw/crawl4ai/{key}.response.bin",
                         html_representation="DECODED_HTML_NORMALIZED_NEWLINES; EXACT_RESPONSE_IN_RAW_BYTES",
                         text_basis="CLEANED_DOM_TEXT", evidence_offset_unit="UNICODE_CHARACTER",
                         permission=self.permission, robots_checked=True, mode=self.config.get("mode", "http"),
                         js_diagnosis=self.config.get("js_diagnosis"), extract_signals=False,
                         css_selector=self.config.get("css_selector"),
                         fields_status="UNKNOWN_PENDING_EXISTING_PARSER_AND_HUMAN_REVIEW",
                         structured_fields=extract_fields(rendered_html or html, self.config.get("field_css")),
                         resources={"bytes": client.bytes + render.get("bytes", 0), "requests": client.requests + render.get("requests", 0),
                                    "peak_rss_bytes": render.get("peak_rss_bytes"),
                                    "elapsed_seconds": round(time.monotonic()-started, 3)},
                         render_status={k:v for k,v in render.items() if k != "html"})
            if rendered_html:
                extra.update(rendered_html_path=f"data/raw/crawl4ai/{key}.rendered.html", rendered_html_hash=digest(rendered_html))
            item = CollectedItem(url=self.url, canonical_url=response.final_url, title=title,
                                 raw_text=cleaned, published_at=(datetime.fromisoformat(extra['structured_fields']['published_at']['value']) if extra['structured_fields']['published_at'].get('value') else None),
                                 http_status=response.status, content_type=response.content_type, extra=extra)
            self.log(self.url.split("?")[0], "PARSE_SUCCESS", int((time.monotonic()-started)*1000))
            return [item]
        except CrawlStopped as exc:
            self.log(self.url.split("?")[0], "STOPPED", reason=str(exc))
            raise


def re_access_barrier(html: str) -> bool:
    import re
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select('input[type="password"], .g-recaptcha, #captcha') or
                re.search(r"(?:验证后访问|请完成验证码|登录后查看|付费后阅读|access denied|verify you are human)", soup.get_text(" "), re.I))
