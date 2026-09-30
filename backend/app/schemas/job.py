from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class JobCreate(ORMModel):
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=300)
    query: str | None = None
    keywords_json: list = Field(default_factory=list)


class JobRead(ORMModel):
    id: str
    source_id: str | None
    name: str
    query: str | None
    keywords_json: list
    status: str
    progress: int
    started_at: datetime | None
    finished_at: datetime | None
    record_count: int
    error_count: int
    error_message: str | None
    duration_seconds: float | None
    created_at: datetime
    updated_at: datetime
