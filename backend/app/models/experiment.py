from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
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

    # ---- T06：完整实验定义 ----
    value_proposition: Mapped[str | None] = mapped_column(Text)
    offer_description: Mapped[str | None] = mapped_column(Text)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_currency: Mapped[str | None] = mapped_column(String(10))
    price_type: Mapped[str | None] = mapped_column(String(30))
    # 实验目标（我们设定的目标，不是市场事实）
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_replies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_meetings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_quotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_pilots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_criteria: Mapped[str | None] = mapped_column(Text)
    # actual_* 不落库：真实值由 targets/interactions/quotes 实时统计（metrics 服务），避免双写不一致
    failure_criteria: Mapped[str | None] = mapped_column(Text)

    target_company_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    # T07：实验开始时冻结的快照（假设/评分模型版本/报价假设/目标筛选规则），保证结果可解释
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    conclusion: Mapped[str | None] = mapped_column(String(30), index=True)
    conclusion_notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    market: Mapped["Market | None"] = relationship(back_populates="experiments")
    experiment_opportunities: Mapped[list["ExperimentOpportunity"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="experiment")
    targets: Mapped[list["ExperimentTarget"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="experiment")


class ExperimentOpportunity(Base):
    __tablename__ = "experiment_opportunities"
    __table_args__ = (UniqueConstraint("experiment_id", "opportunity_id", name="uq_experiment_opportunity"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("exo"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    experiment: Mapped[Experiment] = relationship(back_populates="experiment_opportunities")


class ExperimentTarget(TimestampMixin, Base):
    """实验验证目标企业：一次真实人工验证的单位（漏斗按 target=企业计数，不按互动条数）。"""

    __tablename__ = "experiment_targets"
    __table_args__ = (UniqueConstraint("experiment_id", "company_id", name="uq_experiment_target"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("tgt"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True)
    # 到达过的最远主流程阶段（漏斗统计依据；状态可回退但到达过就算）
    reached_stage: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    # T07：选择理由（高Intent/新鲜信号/高证据/高可达 + 具体数值），选择必须可解释
    selection_reason: Mapped[list] = mapped_column(JSON, default=list, server_default="[]", nullable=False)
    added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_action: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)

    experiment: Mapped[Experiment] = relationship(back_populates="targets")
    company: Mapped["Company"] = relationship()
    opportunity: Mapped["Opportunity | None"] = relationship()
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="target")
    outcome: Mapped["ExperimentOutcome | None"] = relationship(back_populates="target", uselist=False, cascade="all, delete-orphan")


class Interaction(TimestampMixin, Base):
    """每一次真实商业动作的记录（人工执行；系统不自动外发）。"""

    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("int"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    experiment_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id", ondelete="SET NULL"), index=True)
    # T06：关联验证目标与联系人（真实来源联系人，不伪造）
    target_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_targets.id", ondelete="SET NULL"), index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("company_contacts.id", ondelete="SET NULL"), index=True)

    # T06：结构化动作（新）；channel/contact_at 等旧字段保留兼容
    interaction_type: Mapped[str | None] = mapped_column(String(30), index=True)
    direction: Mapped[str | None] = mapped_column(String(20), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    subject: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(50), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(30))
    next_action: Mapped[str | None] = mapped_column(String(300))
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(100))
    evidence_attachment: Mapped[str | None] = mapped_column(Text)  # 附件路径引用，不写内容进日志

    # ---- 既有字段（T04 引入，保留兼容）----
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")
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
    target: Mapped["ExperimentTarget | None"] = relationship(back_populates="interactions")
    contact: Mapped["CompanyContact | None"] = relationship()


class Quote(TimestampMixin, Base):
    """真实报价记录；报价金额永远不是收入。"""

    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("qte"))
    experiment_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id", ondelete="SET NULL"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_targets.id", ondelete="SET NULL"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    billing_type: Mapped[str | None] = mapped_column(String(30))
    scope: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response: Mapped[str | None] = mapped_column(Text)

    experiment: Mapped[Experiment | None] = relationship(back_populates="quotes")


class ExperimentOutcome(TimestampMixin, Base):
    """验证目标企业的最终结果（终态快照；驱动 Opportunity Feedback）。"""

    __tablename__ = "experiment_outcomes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("out"))
    target_id: Mapped[str] = mapped_column(ForeignKey("experiment_targets.id", ondelete="CASCADE"), index=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    final_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 真实合同/到账收入；报价金额不得写入
    contract_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    received_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    reject_reason: Mapped[str | None] = mapped_column(String(50), index=True)
    pain_confirmed: Mapped[bool | None] = mapped_column(Boolean)
    budget_confirmed: Mapped[bool | None] = mapped_column(Boolean)
    intent_confirmed: Mapped[bool | None] = mapped_column(Boolean)
    solution_fit_confirmed: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    target: Mapped[ExperimentTarget] = relationship(back_populates="outcome")
