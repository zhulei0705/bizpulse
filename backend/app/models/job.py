from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class CollectionJob(TimestampMixin, Base):
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("job"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(30), default="MANUAL", nullable=False, index=True)  # MANUAL / SCHEDULED / INGEST / IMPORT
    query: Mapped[str | None] = mapped_column(Text)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # PENDING / RUNNING / SUCCESS / PARTIAL_SUCCESS / FAILED / CANCELLED
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 兼容字段 = items_created
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    # T03：逐 URL 采集明细日志（url/status/latency/items/error），不只一个 SUCCESS
    run_log_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    source: Mapped["Source | None"] = relationship()
