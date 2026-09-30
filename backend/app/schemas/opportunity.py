from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import ORMModel


class OpportunityCreate(ORMModel):
    company_id: str
    market_id: str | None = None
    primary_signal_id: str | None = None
    pain_point_id: str | None = None
    title: str = Field(min_length=1, max_length=500)
    problem: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    value_proposition: str | None = None
    trigger_event: str | None = None
    purchase_intent: str | None = None
    estimated_budget_level: str | None = None
    budget_hypothesis_text: str | None = None
    pain_score: int = Field(default=0, ge=0, le=100)
    budget_score: int = Field(default=0, ge=0, le=100)
    intent_score: int = Field(default=0, ge=0, le=100)
    urgency_score: int = Field(default=0, ge=0, le=100)
    agent_fit_score: int = Field(default=0, ge=0, le=100)
    reachability_score: int = Field(default=0, ge=0, le=100)
    evidence_score: int = Field(default=0, ge=0, le=100)
    confidence: int = Field(default=0, ge=0, le=100)
    stage: str = "NEW"
    owner: str | None = None


class OpportunityRead(ORMModel):
    id: str
    company_id: str
    market_id: str | None
    primary_signal_id: str | None
    pain_point_id: str | None
    title: str
    problem: str
    solution: str
    value_proposition: str | None
    trigger_event: str | None
    purchase_intent: str | None
    estimated_budget_level: str | None
    budget_hypothesis_text: str | None
    pain_score: int
    budget_score: int
    intent_score: int
    urgency_score: int
    agent_fit_score: int
    reachability_score: int
    evidence_score: int
    total_score: float
    grade: str
    confidence: int
    stage: str
    status: str
    owner: str | None
    review_status: str = "PENDING"
    reviewed_at: datetime | None = None
    review_note: str | None = None
    reviewed_by: str | None = None
    created_at: datetime
    updated_at: datetime


class OpportunityStageUpdate(ORMModel):
    stage: str
    owner: str | None = None


class OpportunityEvidenceCreate(ORMModel):
    source_record_id: str | None = None
    signal_id: str | None = None
    evidence_type: str = "SOURCE"
    evidence_excerpt: str | None = None
    weight: int = Field(default=1, ge=1, le=10)


class OpportunityReviewUpdates(ORMModel):
    """action=edit 时允许修改的字段。分数变更会触发后端重新计算总分。"""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    problem: str | None = Field(default=None, min_length=1)
    solution: str | None = Field(default=None, min_length=1)
    value_proposition: str | None = None
    trigger_event: str | None = None
    purchase_intent: str | None = None
    pain_score: int | None = Field(default=None, ge=0, le=100)
    budget_score: int | None = Field(default=None, ge=0, le=100)
    intent_score: int | None = Field(default=None, ge=0, le=100)
    urgency_score: int | None = Field(default=None, ge=0, le=100)
    agent_fit_score: int | None = Field(default=None, ge=0, le=100)
    reachability_score: int | None = Field(default=None, ge=0, le=100)
    evidence_score: int | None = Field(default=None, ge=0, le=100)
    owner: str | None = None


class OpportunityReviewRequest(ORMModel):
    action: str  # approve | reject | edit | ready
    note: str | None = None
    updates: OpportunityReviewUpdates | None = None

    @model_validator(mode="after")
    def _validate(self) -> "OpportunityReviewRequest":
        if self.action not in {"approve", "reject", "edit", "ready"}:
            raise ValueError("action 必须是 approve / reject / edit / ready 之一")
        return self
