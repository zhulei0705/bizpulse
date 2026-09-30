from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("opp"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    primary_signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id", ondelete="SET NULL"), index=True)
    pain_point_id: Mapped[str | None] = mapped_column(ForeignKey("pain_points.id", ondelete="SET NULL"), index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    value_proposition: Mapped[str | None] = mapped_column(Text)
    trigger_event: Mapped[str | None] = mapped_column(Text)
    purchase_intent: Mapped[str | None] = mapped_column(String(50))
    estimated_budget_level: Mapped[str | None] = mapped_column(String(50))
    budget_hypothesis_text: Mapped[str | None] = mapped_column(Text)

    pain_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intent_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urgency_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_fit_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reachability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False, index=True)
    grade: Mapped[str] = mapped_column(String(5), default="D", nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    owner: Mapped[str | None] = mapped_column(String(200))

    # 人工审核记录
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(100))

    company: Mapped["Company"] = relationship(back_populates="opportunities")
    market: Mapped["Market | None"] = relationship(back_populates="opportunities")
    primary_signal: Mapped["Signal | None"] = relationship()
    pain_point: Mapped["PainPoint | None"] = relationship()
    evidences: Mapped[list["OpportunityEvidence"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="opportunity")


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("oev"))
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id", ondelete="SET NULL"), index=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id", ondelete="SET NULL"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(50), default="SOURCE", nullable=False)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    opportunity: Mapped[Opportunity] = relationship(back_populates="evidences")
