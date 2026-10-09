from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class CollectionCampaign(TimestampMixin, Base):
    """T08 采集战役：某个市场的数据扩充计划（只做采集计划，不直接创造企业）。

    只有真正发现并通过真实性 Gate 的 Company 才能进入正式库。
    """

    __tablename__ = "collection_campaigns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cmpn"))
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    market: Mapped[str | None] = mapped_column(String(200))
    keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    seed_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    target_company_count: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    progress_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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

    # ---- T08：企业池扩充 ----
    # 组织类型（COMPANY/GOVERNMENT/UNIVERSITY/...），通过真实来源判断；无法确认保持 UNKNOWN
    organization_type: Mapped[str] = mapped_column(String(30), default="UNKNOWN", nullable=False, index=True)
    # 企业验证状态：UNVERIFIED（仅名称）/ PUBLIC_SOURCE_VERIFIED（可信官方公开来源）/ WEBSITE_VERIFIED（官网验证）
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", nullable=False, index=True)
    # 代码计算的数据质量分（0-100；不让 LLM 打分）
    company_data_quality: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 发现来源（真实公开目录/公告 URL，可追溯）
    discovery_source_url: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    """企业联系人：只能来自公开信息或用户人工录入（NO_FAKE_CONTACT）。

    verification_status 语义：VERIFIED_PUBLIC（有公开来源并核实）/ USER_PROVIDED（用户合法获得并录入）
    才可作为正式联系渠道；无来源不得标记 VERIFIED_PUBLIC（服务层强制）。
    """

    __tablename__ = "company_contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ctc"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    public_contact: Mapped[str | None] = mapped_column(Text)
    # T06：结构化联系方式与来源（禁止猜测邮箱/电话）
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    public_profile_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id", ondelete="SET NULL"), index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", server_default="UNVERIFIED", nullable=False, index=True)
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # T08.0 P0-6：联系人角色区分（PURCHASER_CONTACT/AGENCY_CONTACT/PROJECT_CONTACT）与所属组织
    contact_type: Mapped[str] = mapped_column(String(30), default="UNCLASSIFIED", server_default="UNCLASSIFIED", nullable=False, index=True)
    organization_name: Mapped[str | None] = mapped_column(String(300))
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company: Mapped[Company] = relationship(back_populates="contacts")
