from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class CompanyCreate(ORMModel):
    company_name: str = Field(min_length=1, max_length=300)
    normalized_name: str | None = None
    website: str | None = None
    domain: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    country: str | None = None
    province: str | None = None
    city: str | None = None
    employee_range: str | None = None
    business_model: str | None = None
    main_products: list = Field(default_factory=list)
    main_markets: list = Field(default_factory=list)
    company_description: str | None = None


class CompanyUpdate(ORMModel):
    website: str | None = None
    domain: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    country: str | None = None
    province: str | None = None
    city: str | None = None
    employee_range: str | None = None
    business_model: str | None = None
    main_products: list | None = None
    main_markets: list | None = None
    company_description: str | None = None
    status: str | None = None


class CompanyRead(ORMModel):
    id: str
    company_name: str
    normalized_name: str
    website: str | None
    domain: str | None
    industry: str | None
    sub_industry: str | None
    country: str | None
    province: str | None
    city: str | None
    employee_range: str | None
    business_model: str | None
    main_products: list
    main_markets: list
    company_description: str | None
    pulse_score: float | None
    opportunity_level: str | None
    status: str
    source_count: int
    created_at: datetime
    updated_at: datetime
