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
    offer_name: str | None = None
    pricing_hypothesis: str | None = None
    target_company_count: int = Field(default=0, ge=0)
    status: str = "DRAFT"
    started_at: datetime | None = None


class ExperimentRead(ORMModel):
    id: str
    name: str
    description: str | None
    market_id: str | None
    hypothesis: str
    target_customer: str | None
    offer_name: str | None
    pricing_hypothesis: str | None
    target_company_count: int
    status: str
    conclusion: str | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InteractionCreate(ORMModel):
    company_id: str
    opportunity_id: str | None = None
    experiment_id: str | None = None
    channel: str
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


class ExperimentMetrics(ORMModel):
    contacted: int = 0
    replied: int = 0
    meetings: int = 0
    quotes: int = 0
    deals: int = 0
    revenue: Decimal = Decimal("0")
    reply_rate: float = 0
    meeting_rate: float = 0
    quote_rate: float = 0
    close_rate: float = 0
