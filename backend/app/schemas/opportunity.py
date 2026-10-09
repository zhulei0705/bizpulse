from datetime import datetime

from pydantic import Field, model_validator

from app.core.constants import OPPORTUNITY_REJECT_REASONS
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
    # T05/T06：可解释字段（创建时可携带；候选转换路径直接写入）
    why_now: str | None = None
    risk_notes: list = []
    validation_questions: list = []


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
    grade_cap_reason: str | None = None
    confidence: int
    stage: str
    status: str
    owner: str | None
    # T05 新增（详情可解释性）
    why_now: str | None = None
    risk_notes: list = []
    validation_questions: list = []
    score_breakdown: dict = {}
    recommended_next_action: str | None = None
    fingerprint: str | None = None
    last_signal_at: datetime | None = None
    last_evidence_at: datetime | None = None
    expires_at: datetime | None = None
    stale_reason: str | None = None
    reject_reason: str | None = None
    candidate_id: str | None = None
    review_status: str = "PENDING"
    reviewed_at: datetime | None = None
    review_note: str | None = None
    reviewed_by: str | None = None
    # T06 真实验证信息
    observed_intent: str | None = None
    confirmed_budget: str | None = None
    last_contacted_at: datetime | None = None
    contact_count: int = 0
    created_at: datetime
    updated_at: datetime


class OpportunityStageUpdate(ORMModel):
    stage: str
    owner: str | None = None


class OpportunityStageChangeRequest(ORMModel):
    """T06 阶段流转请求：含状态机保护所需的辅助字段。"""

    stage: str
    owner: str | None = None
    reject_reason: str | None = None
    contract_amount: float | None = Field(default=None, ge=0)
    force: bool = False
    note: str | None = None


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
    action: str  # approve | reject | edit | ready | need_more_evidence
    note: str | None = None
    updates: OpportunityReviewUpdates | None = None
    # T05：驳回原因（reject 时建议填写，取值必须是 OPPORTUNITY_REJECT_REASONS 枚举）
    reject_reason: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "OpportunityReviewRequest":
        if self.action not in {"approve", "reject", "edit", "ready", "need_more_evidence"}:
            raise ValueError("action 必须是 approve / reject / edit / ready / need_more_evidence 之一")
        if self.reject_reason is not None and self.reject_reason not in OPPORTUNITY_REJECT_REASONS:
            raise ValueError("reject_reason 必须是 OPPORTUNITY_REJECT_REASONS 枚举值")
        return self
