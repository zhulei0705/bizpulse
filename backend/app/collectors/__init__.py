from app.collectors.base import CollectedItem, CollectorAdapter
from app.collectors.registry import available_collectors, get_adapter, register
from app.collectors.rss import RSSCollector
from app.collectors.web import ManualUrlCollector, WebPageCollector

__all__ = [
    "CollectedItem", "CollectorAdapter", "RSSCollector", "WebPageCollector",
    "ManualUrlCollector", "get_adapter", "register", "available_collectors",
]
