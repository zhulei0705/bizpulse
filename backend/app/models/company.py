from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class CompanyMarket(Base):
    __tablename__ = "company_markets"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), primary_key=True)


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cmp"))
    company_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(150), index=True)
    sub_industry: Mapped[str | None] = mapped_column(String(150), index=True)
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    province: Mapped[str | None] = mapped_column(String(100), index=True)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    employee_range: Mapped[str | None] = mapped_column(String(100))
    business_model: Mapped[str | None] = mapped_column(String(100))
    main_products: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    main_markets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    company_description: Mapped[str | None] = mapped_column(Text)
    pulse_score: Mapped[float | None] = mapped_column(Float)
    opportunity_level: Mapped[str | None] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    aliases: Mapped[list["CompanyAlias"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    contacts: Mapped[list["CompanyContact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    source_records: Mapped[list["SourceRecord"]] = relationship(back_populates="company")
    signals: Mapped[list["Signal"]] = relationship(back_populates="company")
    pain_points: Mapped[list["PainPoint"]] = relationship(back_populates="company")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="company")
    markets: Mapped[list["Market"]] = relationship(secondary="company_markets", back_populates="companies")


class CompanyAlias(Base):
    __tablename__ = "company_aliases"
    __table_args__ = (UniqueConstraint("company_id", "normalized_alias", name="uq_company_alias"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("als"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    company: Mapped[Company] = relationship(back_populates="aliases")


class CompanyContact(TimestampMixin, Base):
    __tablename__ = "company_contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ctc"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    public_contact: Mapped[str | None] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id", ondelete="SET NULL"), index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company: Mapped[Company] = relationship(back_populates="contacts")
