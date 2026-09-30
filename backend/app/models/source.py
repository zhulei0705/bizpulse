from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id, utcnow


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("src"))
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    base_url: Mapped[str | None] = mapped_column(Text)
    reliability_grade: Mapped[str] = mapped_column(String(1), default="C", nullable=False)
    reliability_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    collector_type: Mapped[str | None] = mapped_column(String(100))
    collection_frequency: Mapped[str | None] = mapped_column(String(100))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_rate: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    # T03：采集配置（Adapter 参数：超时/条数/开始页等），级别由配置决定、禁止 AI 自定
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    records: Mapped[list["SourceRecord"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (UniqueConstraint("source_id", "content_hash", name="uq_source_record_hash"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("rec"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # T03：规范化 URL（去 utm/fragment/大小写），用于同页识别与版本对比
    canonical_url: Mapped[str | None] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_html_path: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str | None] = mapped_column(String(20))
    # 真实数据验证机制：人工审核通过后标记 VERIFIED
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", server_default="UNVERIFIED", nullable=False, index=True)
    source_reliability: Mapped[str | None] = mapped_column(String(1))  # 采集时的来源等级快照 A/B/C/D
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # T03：企业关联状态（EXACT/HIGH_CONFIDENCE/POSSIBLE/UNKNOWN/UNRESOLVED/USER_LINKED）
    company_resolve_status: Mapped[str] = mapped_column(String(30), default="UNRESOLVED", server_default="UNRESOLVED", nullable=False, index=True)
    # T03：版本机制 —— 同一 canonical_url 内容变化时保留历史（旧版本 is_latest=False）
    parent_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id", ondelete="SET NULL"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # T03：解析失败留痕（不生成假正文）
    parse_status: Mapped[str] = mapped_column(String(20), default="OK", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    # T03：数据过期设计（招聘/采购/新闻非永久有效；本阶段先落字段）
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    source: Mapped[Source] = relationship(back_populates="records")
    company: Mapped["Company | None"] = relationship(back_populates="source_records")
    signals: Mapped[list["Signal"]] = relationship(back_populates="source_record")
