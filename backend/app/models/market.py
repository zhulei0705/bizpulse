from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class Market(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("mkt"))
    market_name: Mapped[str] = mapped_column(String(250), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(250), nullable=False, unique=True, index=True)
    target_customer: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    current_solution: Mapped[str | None] = mapped_column(Text)
    current_cost: Mapped[str | None] = mapped_column(String(200))
    frequency: Mapped[str | None] = mapped_column(String(100))
    willingness_to_pay: Mapped[int | None] = mapped_column(Integer)
    automation_fit: Mapped[int | None] = mapped_column(Integer)
    competition: Mapped[int | None] = mapped_column(Integer)
    entry_difficulty: Mapped[int | None] = mapped_column(Integer)
    market_score: Mapped[float | None] = mapped_column(Float, index=True)
    validation_status: Mapped[str] = mapped_column(String(30), default="OBSERVE", nullable=False, index=True)
    company_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_value_company_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    companies: Mapped[list["Company"]] = relationship(secondary="company_markets", back_populates="markets")
    signals: Mapped[list["Signal"]] = relationship(back_populates="market")
    pain_points: Mapped[list["PainPoint"]] = relationship(back_populates="market")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="market")
    experiments: Mapped[list["Experiment"]] = relationship(back_populates="market")
