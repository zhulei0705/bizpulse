"""RSSCollector：RSS / Atom 订阅采集器（feedparser）。

每个 Entry 生成独立 SourceRecord 候选；失败 Entry 记 parse_status=FAILED。
不访问登录内容、不绕过任何访问控制。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import httpx

from app.collectors.base import CollectedItem, CollectorAdapter
from app.collectors.urlutils import canonicalize_url
from app.core.config import settings
from app.services.extractor import URLSafetyError, validate_public_url


class RSSCollector(CollectorAdapter):
    collector_type = "rss"

    def validate_config(self) -> None:
        if not (self.source.base_url or self.config.get("feed_url")):
            raise ValueError("rss 采集器需要 base_url（feed 地址）")

    def _fetch_feed(self) -> str:
        feed_url = (self.config.get("feed_url") or self.source.base_url or "").strip()
        validate_public_url(feed_url)
        headers = {"User-Agent": self.config.get("user_agent") or settings.ingest_user_agent}
        with httpx.Client(timeout=self.config.get("timeout", settings.ingest_timeout_seconds), follow_redirects=True, headers=headers) as client:
            response = client.get(feed_url)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        for key in ("published", "updated", "created"):
            value = entry.get(key)
            if not value:
                continue
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _entry_link(feed_url: str, entry) -> str | None:
        link = entry.get("link")
        if not link:
            return None
        if link.startswith("http"):
            return link
        # 相对链接回退到 feed 域名
        origin = urlparse(feed_url)
        return f"{origin.scheme}://{origin.netloc}{link}"

    def fetch(self) -> list[CollectedItem]:
        feed_url = (self.config.get("feed_url") or self.source.base_url or "").strip()
        started = time.perf_counter()
        try:
            raw = self._fetch_feed()
        except (httpx.HTTPError, URLSafetyError, RuntimeError) as exc:
            self.log(feed_url, "FAILED", int((time.perf_counter() - started) * 1000), error=str(exc)[:300])
            return [CollectedItem(url=feed_url, canonical_url=canonicalize_url(feed_url), parse_status="FAILED", error_message=str(exc)[:500])]

        latency = int((time.perf_counter() - started) * 1000)
        parsed = feedparser.parse(raw)
        entries = parsed.entries or []
        self.log(feed_url, f"ENTRIES_{len(entries)}", latency)
        limit = int(self.config.get("max_items", 20))

        items: list[CollectedItem] = []
        for entry in entries[:limit]:
            link = self._entry_link(feed_url, entry)
            if not link:
                continue
            text_parts = []
            for key in ("description", "summary", "content"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    text_parts.append(value.strip())
                elif isinstance(value, list):
                    text_parts.extend(str(c.get("value", "")).strip() for c in value if isinstance(c, dict))
            raw_text = "\n".join(p for p in text_parts if p) or None
            ok = bool((entry.get("title") or "").strip() or raw_text)
            items.append(CollectedItem(
                url=link,
                canonical_url=canonicalize_url(link),
                title=(entry.get("title") or "").strip() or None,
                raw_text=raw_text,
                published_at=self._parse_published(entry),
                http_status=200,
                content_type="application/rss+xml",
                parse_status="OK" if ok else "FAILED",
                error_message=None if ok else "RSS 条目无标题且无正文",
                author=(entry.get("author") or None),
                extra={"feed_url": feed_url},
            ))
        return items
