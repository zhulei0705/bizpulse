"""CollectorAdapter —— 统一采集器抽象（T03）。

所有数据源（网页/RSS/政府/人工导入）通过 Adapter 扩展；
禁止在业务代码中为单个来源写特殊逻辑。

生命周期：validate_config → fetch → parse → normalize → build_records
产物：CollectedItem（规范化后的原始记录，入库前不含任何 AI 生成内容）。
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CollectedItem:
    """一条规范化采集结果（对应一个 SourceRecord 候选）。"""

    url: str
    canonical_url: str
    title: str | None = None
    raw_text: str | None = None
    published_at: datetime | None = None
    http_status: int | None = None
    content_type: str | None = None
    language: str | None = None
    author: str | None = None
    parse_status: str = "OK"           # OK / FAILED
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # Adapter 私有补充字段

    def content_hash(self) -> str:
        normalized = "\n".join(part.strip() for part in (self.canonical_url, self.title or "", self.raw_text or "") if part)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class CollectorAdapter(ABC):
    """采集器统一接口。子类通过 registry 注册 collector_type。"""

    #: 注册名（sources.collector_type 与此匹配）
    collector_type: str = ""

    def __init__(self, source, config: dict | None = None) -> None:
        self.source = source
        self.config = {**(config or {})}
        self.run_log: list[dict] = []  # 逐 URL 明细：url/status/latency/error

    # ---- 接口 ----
    @abstractmethod
    def validate_config(self) -> None:
        """配置校验失败抛 ValueError（在创建/执行前调用）。"""

    @abstractmethod
    def fetch(self) -> list[CollectedItem]:
        """真实访问数据源并返回规范化条目（失败条目带 parse_status=FAILED）。"""

    # ---- 可选覆盖 ----
    def parse(self, payload: Any) -> list[CollectedItem]:  # noqa: ARG002 - 默认 fetch 内完成
        return []

    def normalize(self) -> None:
        return None

    def build_records(self) -> list[CollectedItem]:
        """默认实现：fetch 即产出记录（RSS 等多页源可覆盖以合并多轮 fetch）。"""
        return self.fetch()

    # ---- 公共工具 ----
    def log(self, url: str, status: str, latency_ms: int = 0, **extra: Any) -> None:
        entry = {"url": url, "status": status, "latency_ms": latency_ms, "at": datetime.now(timezone.utc).isoformat(), **extra}
        self.run_log.append(entry)
        logger.info("collector=%s source=%s %s %s (%dms)", self.collector_type, getattr(self.source, "id", "?"), status, url, latency_ms)
