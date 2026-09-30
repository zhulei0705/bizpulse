from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class SourceCreate(ORMModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=50)
    base_url: str | None = None
    reliability_grade: str = "C"
    reliability_score: int = Field(default=50, ge=0, le=100)
    enabled: bool = True
    collector_type: str | None = None
    collection_frequency: str | None = None
    notes: str | None = None
    config_json: dict = Field(default_factory=dict)


class SourceUpdate(ORMModel):
    name: str | None = None
    base_url: str | None = None
    reliability_grade: str | None = None
    reliability_score: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None
    collector_type: str | None = None
    collection_frequency: str | None = None
    notes: str | None = None
    config_json: dict | None = None


class SourceRead(ORMModel):
    id: str
    name: str
    source_type: str
    base_url: str | None
    reliability_grade: str
    reliability_score: int
    enabled: bool
    collector_type: str | None
    collection_frequency: str | None
    last_run_at: datetime | None
    last_success_at: datetime | None = None
    success_rate: float | None
    notes: str | None
    config_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SourceRecordCreate(ORMModel):
    company_id: str | None = None
    url: str = Field(min_length=1)
    title: str | None = None
    raw_text: str | None = None
    raw_html_path: str | None = None
    published_at: datetime | None = None
    content_hash: str | None = None
    http_status: int | None = None
    language: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class SourceRecordRead(ORMModel):
    id: str
    source_id: str
    company_id: str | None
    url: str
    canonical_url: str | None = None
    title: str | None
    published_at: datetime | None
    collected_at: datetime
    content_hash: str
    http_status: int | None
    content_type: str | None = None
    language: str | None
    verification_status: str = "UNVERIFIED"
    source_reliability: str | None = None
    last_verified_at: datetime | None = None
    company_resolve_status: str = "UNRESOLVED"
    version_number: int = 1
    is_latest: bool = True
    parent_record_id: str | None = None
    parse_status: str = "OK"
    is_active: bool = True
    metadata_json: dict
