from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("exp"))
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    target_customer: Mapped[str | None] = mapped_column(Text)
    offer_name: Mapped[str | None] = mapped_column(String(300))
    pricing_hypothesis: Mapped[str | None] = mapped_column(String(300))
    target_company_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    conclusion: Mapped[str | None] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    market: Mapped["Market | None"] = relationship(back_populates="experiments")
    experiment_opportunities: Mapped[list["ExperimentOpportunity"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="experiment")


class ExperimentOpportunity(Base):
    __tablename__ = "experiment_opportunities"
    __table_args__ = (UniqueConstraint("experiment_id", "opportunity_id", name="uq_experiment_opportunity"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("exo"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    experiment: Mapped[Experiment] = relationship(back_populates="experiment_opportunities")


class Interaction(TimestampMixin, Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("int"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    experiment_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id", ondelete="SET NULL"), index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_title: Mapped[str | None] = mapped_column(String(200))
    response_summary: Mapped[str | None] = mapped_column(Text)
    response_type: Mapped[str | None] = mapped_column(String(50), index=True)
    meeting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quote_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    deal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reject_reason: Mapped[str | None] = mapped_column(String(80), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="interactions")
    experiment: Mapped[Experiment | None] = relationship(back_populates="interactions")
