from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class PainPointCreate(ORMModel):
    company_id: str
    market_id: str | None = None
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    confidence: int = Field(default=0, ge=0, le=100)
    reason: str | None = None
    status: str = "INFERRED"


class PainPointRead(ORMModel):
    id: str
    company_id: str
    market_id: str | None
    category: str
    description: str
    confidence: int
    reason: str | None
    status: str
    created_at: datetime
    updated_at: datetime
