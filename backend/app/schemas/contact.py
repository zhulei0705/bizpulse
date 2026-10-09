from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class CompanyContactCreate(ORMModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    public_contact: str | None = None
    email: str | None = None
    phone: str | None = None
    public_profile_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    source_record_id: str | None = None
    verification_status: str = "UNVERIFIED"
    is_decision_maker: bool = False
    confidence: int = Field(default=0, ge=0, le=100)
    # 兼容旧字段：verified_public=true 等价于 verification_status=VERIFIED_PUBLIC
    verified_public: bool = False


class CompanyContactUpdate(ORMModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    public_contact: str | None = None
    email: str | None = None
    phone: str | None = None
    public_profile_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    source_record_id: str | None = None
    verification_status: str | None = None
    is_decision_maker: bool | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)


class CompanyContactRead(ORMModel):
    id: str
    company_id: str
    name: str | None
    title: str | None
    department: str | None
    public_contact: str | None
    email: str | None = None
    phone: str | None = None
    public_profile_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    source_record_id: str | None
    verification_status: str = "UNVERIFIED"
    is_decision_maker: bool = False
    contact_type: str = "UNCLASSIFIED"
    organization_name: str | None = None
    confidence: int
    verified_public: bool
    created_at: datetime
    updated_at: datetime
