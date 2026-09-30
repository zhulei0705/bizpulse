from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_id, TimestampMixin, utcnow


class Signal(TimestampMixin, Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sig"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("source_records.id", ondelete="CASCADE"), index=True)
    signal_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reliability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    heat_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="VALID", nullable=False, index=True)
    fact_or_inference: Mapped[str] = mapped_column(String(20), default="FACT", nullable=False)
    # 真实数据验证机制：UNVERIFIED / VERIFIED
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", server_default="UNVERIFIED", nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="signals")
    market: Mapped["Market | None"] = relationship(back_populates="signals")
    source_record: Mapped["SourceRecord"] = relationship(back_populates="signals")
