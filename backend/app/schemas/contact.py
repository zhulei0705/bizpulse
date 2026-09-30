from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class CompanyContactCreate(ORMModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    public_contact: str | None = None
    source_record_id: str | None = None
    confidence: int = Field(default=0, ge=0, le=100)
    verified_public: bool = False


class CompanyContactRead(ORMModel):
    id: str
    company_id: str
    name: str | None
    title: str | None
    department: str | None
    public_contact: str | None
    source_record_id: str | None
    confidence: int
    verified_public: bool
    created_at: datetime
    updated_at: datetime
