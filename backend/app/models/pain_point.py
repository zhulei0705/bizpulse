from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class PainPoint(TimestampMixin, Base):
    __tablename__ = "pain_points"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("pain"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="INFERRED", nullable=False, index=True)

    company: Mapped["Company"] = relationship(back_populates="pain_points")
    market: Mapped["Market | None"] = relationship(back_populates="pain_points")
    evidences: Mapped[list["PainPointEvidence"]] = relationship(back_populates="pain_point", cascade="all, delete-orphan")


class PainPointEvidence(Base):
    __tablename__ = "pain_point_evidences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("pev"))
    pain_point_id: Mapped[str] = mapped_column(ForeignKey("pain_points.id", ondelete="CASCADE"), index=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id", ondelete="SET NULL"), index=True)
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id", ondelete="SET NULL"), index=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    pain_point: Mapped[PainPoint] = relationship(back_populates="evidences")
