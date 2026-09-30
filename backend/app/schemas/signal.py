from datetime import datetime

from pydantic import Field, model_validator

from app.core.constants import SIGNAL_TYPES
from app.schemas.common import ORMModel


class SignalCreate(ORMModel):
    company_id: str
    market_id: str | None = None
    source_record_id: str | None = None
    signal_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    published_at: datetime | None = None
    confidence: int = Field(default=0, ge=0, le=100)
    reliability_score: int = Field(default=0, ge=0, le=100)
    heat_score: float | None = Field(default=None, ge=0, le=100)
    status: str = "VALID"
    fact_or_inference: str = "FACT"
    payload_json: dict = Field(default_factory=dict)
    # 人工录入时允许直接给证据 URL，后端自动生成 SourceRecord（保证可追溯）
    evidence_url: str | None = None
    evidence_title: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "SignalCreate":
        if self.signal_type not in SIGNAL_TYPES:
            allowed = ", ".join(sorted(SIGNAL_TYPES))
            raise ValueError(f"signal_type 必须是以下枚举之一：{allowed}")
        if self.fact_or_inference not in {"FACT", "INFERENCE"}:
            raise ValueError("fact_or_inference 必须是 FACT 或 INFERENCE")
        if not self.source_record_id and not self.evidence_url:
            raise ValueError("必须提供 source_record_id 或 evidence_url 之一，保证信号可追溯")
        return self


class SignalRead(ORMModel):
    id: str
    company_id: str
    market_id: str | None
    source_record_id: str
    signal_type: str
    title: str
    description: str | None
    published_at: datetime | None
    collected_at: datetime
    confidence: int
    reliability_score: int
    heat_score: float | None
    status: str
    fact_or_inference: str
    verification_status: str = "UNVERIFIED"
    payload_json: dict
    created_at: datetime | None = None