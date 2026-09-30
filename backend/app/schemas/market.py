from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class MarketCreate(ORMModel):
    market_name: str = Field(min_length=1, max_length=250)
    slug: str = Field(min_length=1, max_length=250)
    target_customer: str | None = None
    problem: str | None = None
    current_solution: str | None = None
    current_cost: str | None = None
    frequency: str | None = None
    willingness_to_pay: int | None = Field(default=None, ge=0, le=100)
    automation_fit: int | None = Field(default=None, ge=0, le=100)
    competition: int | None = Field(default=None, ge=0, le=100)
    entry_difficulty: int | None = Field(default=None, ge=0, le=100)
    market_score: float | None = Field(default=None, ge=0, le=100)
    validation_status: str = "OBSERVE"


class MarketRead(ORMModel):
    id: str
    market_name: str
    slug: str
    target_customer: str | None
    problem: str | None
    current_solution: str | None
    current_cost: str | None
    frequency: str | None
    willingness_to_pay: int | None
    automation_fit: int | None
    competition: int | None
    entry_difficulty: int | None
    market_score: float | None
    validation_status: str
    company_count: int
    signal_count: int
    high_value_company_count: int
    created_at: datetime
    updated_at: datetime
