from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import ORMModel


class ExperimentCreate(ORMModel):
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    market_id: str | None = None
    hypothesis: str = Field(min_length=1)
    target_customer: str | None = None
    value_proposition: str | None = None
    offer_name: str | None = None
    offer_description: str | None = None
    pricing_hypothesis: str | None = None
    price_amount: Decimal | None = Field(default=None, ge=0)
    price_currency: str | None = Field(default=None, max_length=10)
    price_type: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    target_company_count: int = Field(default=0, ge=0)
    target_contacts: int = Field(default=0, ge=0)
    target_replies: int = Field(default=0, ge=0)
    target_meetings: int = Field(default=0, ge=0)
    target_quotes: int = Field(default=0, ge=0)
    target_pilots: int = Field(default=0, ge=0)
    target_wins: int = Field(default=0, ge=0)
    success_criteria: str | None = None
    failure_criteria: str | None = None
    status: str = "DRAFT"
    started_at: datetime | None = None


class ExperimentUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    market_id: str | None = None
    hypothesis: str | None = None
    target_customer: str | None = None
    value_proposition: str | None = None
    offer_name: str | None = None
    offer_description: str | None = None
    pricing_hypothesis: str | None = None
    price_amount: Decimal | None = Field(default=None, ge=0)
    price_currency: str | None = None
    price_type: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    target_company_count: int | None = Field(default=None, ge=0)
    target_contacts: int | None = Field(default=None, ge=0)
    target_replies: int | None = Field(default=None, ge=0)
    target_meetings: int | None = Field(default=None, ge=0)
    target_quotes: int | None = Field(default=None, ge=0)
    target_pilots: int | None = Field(default=None, ge=0)
    target_wins: int | None = Field(default=None, ge=0)
    success_criteria: str | None = None
    failure_criteria: str | None = None
    status: str | None = None
    conclusion: str | None = None
    conclusion_notes: str | None = None


class ExperimentRead(ORMModel):
    id: str
    name: str
    description: str | None
    market_id: str | None
    hypothesis: str
    target_customer: str | None
    value_proposition: str | None = None
    offer_name: str | None
    offer_description: str | None = None
    pricing_hypothesis: str | None
    price_amount: float | None = None
    price_currency: str | None = None
    price_type: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    target_company_count: int
    target_contacts: int = 0
    target_replies: int = 0
    target_meetings: int = 0
    target_quotes: int = 0
    target_pilots: int = 0
    target_wins: int = 0
    success_criteria: str | None = None
    failure_criteria: str | None = None
    status: str
    conclusion: str | None
    conclusion_notes: str | None = None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExperimentTargetCreate(ORMModel):
    company_id: str
    opportunity_id: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    assigned_to: str | None = None
    notes: str | None = None


class ExperimentTargetUpdate(ORMModel):
    status: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    assigned_to: str | None = None
    notes: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    # 状态流转辅助字段（状态机使用）
    reject_reason: str | None = None
    contract_amount: Decimal | None = Field(default=None, ge=0)
    force: bool = False


class ExperimentTargetRead(ORMModel):
    id: str
    experiment_id: str
    company_id: str
    company_name: str | None = None
    opportunity_id: str | None
    opportunity_title: str | None = None
    opportunity_score: float | None = None
    opportunity_grade: str | None = None
    priority: int
    status: str
    reached_stage: str
    assigned_to: str | None
    selection_reason: list = []
    added_at: datetime | None
    last_interaction_at: datetime | None
    next_action_at: datetime | None
    next_action: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InteractionCreate(ORMModel):
    company_id: str
    opportunity_id: str | None = None
    experiment_id: str | None = None
    target_id: str | None = None
    contact_id: str | None = None
    interaction_type: str | None = None
    direction: str | None = None
    channel: str | None = None
    occurred_at: datetime | None = None
    subject: str | None = Field(default=None, max_length=500)
    summary: str | None = None
    result: str | None = None
    sentiment: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    evidence_attachment: str | None = None
    created_by: str | None = None
    # 旧字段保留兼容（T04 前端仍在用）
    contact_at: datetime | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    response_summary: str | None = None
    response_type: str | None = None
    meeting: bool = False
    quote_amount: Decimal | None = Field(default=None, ge=0)
    deal: bool = False
    revenue: Decimal | None = Field(default=None, ge=0)
    reject_reason: str | None = None
    notes: str | None = None


class InteractionUpdate(ORMModel):
    interaction_type: str | None = None
    direction: str | None = None
    channel: str | None = None
    occurred_at: datetime | None = None
    subject: str | None = None
    summary: str | None = None
    result: str | None = None
    sentiment: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    evidence_attachment: str | None = None
    contact_at: datetime | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    response_summary: str | None = None
    response_type: str | None = None
    meeting: bool | None = None
    quote_amount: Decimal | None = Field(default=None, ge=0)
    deal: bool | None = None
    revenue: Decimal | None = Field(default=None, ge=0)
    reject_reason: str | None = None
    notes: str | None = None


class InteractionRead(ORMModel):
    id: str
    company_id: str
    company_name: str | None = None
    opportunity_id: str | None
    experiment_id: str | None
    target_id: str | None = None
    contact_id: str | None = None
    interaction_type: str | None = None
    direction: str | None = None
    channel: str
    occurred_at: datetime | None = None
    subject: str | None = None
    summary: str | None = None
    result: str | None = None
    sentiment: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    created_by: str | None = None
    evidence_attachment: str | None = None
    contact_at: datetime | None
    contact_name: str | None
    contact_title: str | None
    response_summary: str | None
    response_type: str | None
    meeting: bool
    quote_amount: Decimal | None
    deal: bool
    revenue: Decimal | None
    reject_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class QuoteCreate(ORMModel):
    company_id: str
    experiment_id: str | None = None
    opportunity_id: str | None = None
    target_id: str | None = None
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="CNY", max_length=10)
    billing_type: str | None = None
    scope: str | None = None
    status: str = "DRAFT"
    sent_at: datetime | None = None
    valid_until: datetime | None = None


class QuoteUpdate(ORMModel):
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    billing_type: str | None = None
    scope: str | None = None
    status: str | None = None
    sent_at: datetime | None = None
    valid_until: datetime | None = None
    response: str | None = None


class QuoteRead(ORMModel):
    id: str
    experiment_id: str | None
    company_id: str
    company_name: str | None = None
    opportunity_id: str | None
    target_id: str | None = None
    amount: float
    currency: str
    billing_type: str | None
    scope: str | None
    status: str
    sent_at: datetime | None
    valid_until: datetime | None
    response: str | None
    created_at: datetime
    updated_at: datetime


class AddToExperimentRequest(ORMModel):
    experiment_id: str


class ConfirmPainRequest(ORMModel):
    pain_point_id: str
    note: str | None = None


class ConfirmBudgetRequest(ORMModel):
    budget_text: str = Field(min_length=1, max_length=200)
    interaction_id: str  # 必须引用一条客户来讯（INBOUND）互动作为依据


class StageChangeRequest(ORMModel):
    stage: str
    owner: str | None = None
    reject_reason: str | None = None
    contract_amount: Decimal | None = Field(default=None, ge=0)
    force: bool = False
    note: str | None = None


class ExperimentMetrics(ORMModel):
    targets: int = 0
    contacted: int = 0
    replied: int = 0
    meetings: int = 0
    quotes: int = 0
    pilots: int = 0
    wins: int = 0
    contact_rate: float = 0
    reply_rate: float = 0
    meeting_rate: float = 0
    quote_rate: float = 0
    pilot_rate: float = 0
    close_rate: float = 0
    overall_close_rate: float = 0
    contracted_revenue: float = 0
    received_revenue: float = 0
    revenue: float = 0
    deals: int = 0
