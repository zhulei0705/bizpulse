"""WebPageCollector：公开网页采集器。

- 网络层统一复用 extractor.fetch_public_page（SSRF 防护 + 流式大小限制 + BS4 解析），
  保证全系统只有一套抓取/解析逻辑，测试可统一 Mock；
- 有限重试 + 指数退避；429/5xx 退避重试；401/403 不绕过；
- 原始 HTML 保存到 data/raw/YYYY-MM-DD/{source_id}/，路径写回 raw_html_path；
- 正文为空 → parse_status=FAILED（不生成假正文）。
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.base import CollectedItem, CollectorAdapter
from app.collectors.urlutils import canonicalize_url
from app.core.config import BASE_DIR, settings
from app.services import extractor
from app.services.extractor import URLSafetyError

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_NO_RETRY_STATUS = {401, 403}


def parse_published_raw(raw: str | None) -> datetime | None:
    """发布时间解析（复用 T02 规则；解析失败返回 None，不猜测）。"""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            parsed = datetime.strptime(raw[:19].replace("T", " ").strip(), fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class WebPageCollector(CollectorAdapter):
    collector_type = "web_page"

    def validate_config(self) -> None:
        if not (self.source.base_url or self.config.get("url")):
            raise ValueError("web_page 采集器需要 base_url 或 config.url")

    def _fetch_with_retry(self, url: str):
        """fetch_public_page 复用统一入口（SSRF/大小/解析）；失败按策略重试。"""
        max_retries = int(self.config.get("max_retries", 3))
        base_delay = float(self.config.get("retry_backoff_base", 1.5))
        attempt = 0
        while True:
            attempt += 1
            try:
                return extractor.fetch_public_page(url)
            except URLSafetyError:
                raise  # 安全拒绝：不重试、不绕过
            except Exception as exc:  # noqa: BLE001 - 网络/5xx 等
                status = getattr(exc, "response", None)
                code = getattr(status, "status_code", None)
                if code in _NO_RETRY_STATUS or attempt > max_retries:
                    if attempt > max_retries:
                        self.log(url, "FAILED", error=str(exc)[:200], attempt=attempt)
                    raise
                delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.4), 15)
                self.log(url, f"RETRY_{code or 'NETWORK'}", attempt=attempt)
                time.sleep(delay)

    def _save_raw_html(self, record_id_hint: str, url: str, html: str) -> str:
        day_dir = BASE_DIR / "data" / "raw" / datetime.now(timezone.utc).strftime("%Y-%m-%d") / (self.source.id or record_id_hint)
        day_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-80:] or "page"
        path = day_dir / f"{int(time.time() * 1000)}_{slug}.html"
        path.write_text(html, encoding="utf-8")
        return str(path.relative_to(BASE_DIR))

    def fetch(self) -> list[CollectedItem]:
        url = (self.config.get("url") or self.source.base_url or "").strip()
        started = time.perf_counter()
        try:
            page = self._fetch_with_retry(url)
        except URLSafetyError:
            raise
        except Exception as exc:  # noqa: BLE001 - 记录失败，不生成假数据
            latency = int((time.perf_counter() - started) * 1000)
            self.log(url, "FAILED", latency, error=str(exc)[:300])
            return [CollectedItem(url=url, canonical_url=canonicalize_url(url), parse_status="FAILED", error_message=str(exc)[:500])]

        latency = int((time.perf_counter() - started) * 1000)
        self.log(url, f"HTTP_{page.status_code}", latency)

        raw_path = self._save_raw_html(self.source.id or "adhoc", page.final_url, page.html[: settings.ingest_max_bytes])
        text = (page.text or "").strip()
        parse_status = "OK" if text or (page.title or "").strip() else "FAILED"
        return [CollectedItem(
            url=page.final_url,
            canonical_url=canonicalize_url(page.final_url),
            title=page.title,
            raw_text=page.text or None,
            published_at=parse_published_raw(page.published_at_raw),
            http_status=page.status_code,
            content_type=(page.content_type or "").split(";")[0].strip() or None,
            parse_status=parse_status,
            error_message=None if parse_status == "OK" else "页面无可提取正文内容",
            extra={
                "raw_html_path": raw_path,
                "organization": page.organization,
                "og_site_name": page.og_site_name,
                "meta_description": page.meta_description,
            },
        )]


class ManualUrlCollector(WebPageCollector):
    """手动 URL 分析（ingest/url、ingest/urls 复用同一 Adapter 体系）。"""

    collector_type = "manual_url"

    def validate_config(self) -> None:
        if not self.config.get("url"):
            raise ValueError("manual_url 采集器需要 config.url")
