"""采集器注册表：collector_type → Adapter。

人工导入（CSV/URL 列表）不经过 HTTP 采集，走 manual_import 服务；
此处注册的均为「真实网络采集」Adapter。
"""
from __future__ import annotations

from app.collectors.base import CollectedItem, CollectorAdapter
from app.collectors.rss import RSSCollector
from app.collectors.web import ManualUrlCollector, WebPageCollector

_REGISTRY: dict[str, type[CollectorAdapter]] = {}


def register(adapter_cls: type[CollectorAdapter]) -> type[CollectorAdapter]:
    _REGISTRY[adapter_cls.collector_type] = adapter_cls
    return adapter_cls


register(WebPageCollector)
register(RSSCollector)
register(ManualUrlCollector)


def get_adapter(collector_type: str | None, source, config: dict | None = None) -> CollectorAdapter:
    key = (collector_type or "web_page").strip()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"未知采集器类型：{key}（可用：{', '.join(sorted(_REGISTRY))}）")
    adapter = cls(source, config)
    adapter.validate_config()
    return adapter


def available_collectors() -> list[str]:
    return sorted(_REGISTRY)
