"""OpportunityCandidate —— T05 机会候选。

规则/LLM 组合分析产出的是"候选"，不是正式 Opportunity：
- Evidence 不足 → NEED_MORE_EVIDENCE；
- 评分与解释齐备 → REVIEW（V1 不自动批准）；
- 人工 APPROVED 后 CONVERTED 才生成正式 Opportunity。

铁律：候选必须关联真实 Company + 已批准 Signal；AI 不得凭空生成候选。
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_id


class OpportunityCandidate(TimestampMixin, Base):
    __tablename__ = "opportunity_candidates"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_opportunity_candidate_fingerprint"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ocand"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    bundle_id: Mapped[str | None] = mapped_column(ForeignKey("signal_bundles.id", ondelete="SET NULL"), index=True)
    pain_point_id: Mapped[str | None] = mapped_column(ForeignKey("pain_points.id", ondelete="SET NULL"), index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    problem_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    solution_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    value_hypothesis: Mapped[str | None] = mapped_column(Text)
    trigger_summary: Mapped[str | None] = mapped_column(Text)
    why_now: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    recommended_next_action: Mapped[str | None] = mapped_column(String(50))

    # 参与判断的 Signal（真实已批准信号 id 列表，可审计回溯）
    signal_ids_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    pain_category: Mapped[str | None] = mapped_column(String(100), index=True)
    solution_category: Mapped[str | None] = mapped_column(String(100))

    pain_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intent_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urgency_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_fit_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reachability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False, index=True)
    grade: Mapped[str] = mapped_column(String(5), default="D", nullable=False)
    grade_cap_reason: Mapped[str | None] = mapped_column(String(50))  # LOW_EVIDENCE 等
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 每个分项为什么是这个分（可解释性核心）
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_notes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    validation_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{signal_id, source_record_id, polarity, grade, excerpt}]
    contradicting_evidence_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 状态机：DETECTED / NEED_MORE_EVIDENCE / REVIEW / APPROVED / REJECTED / CONVERTED
    status: Mapped[str] = mapped_column(String(30), default="REVIEW", nullable=False, index=True)
    generated_by: Mapped[str] = mapped_column(String(20), default="RULE", nullable=False)  # RULE / LLM / HYBRID
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    # 输入指纹：company + signal ids + signal hashes + prompt_version → 完全相同跳过重复分析
    analysis_input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    # 去重指纹：company + pain_category + solution_category + 时间窗
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(String(50))
    # CONVERTED 后对应的正式 Opportunity
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)

    company: Mapped["Company"] = relationship()
    pain_point: Mapped["PainPoint | None"] = relationship()
    bundle: Mapped["SignalBundle | None"] = relationship()


class SignalBundle(TimestampMixin, Base):
    """SignalBundle —— 多信号组合（T05）。

    组合规则可解释（规则表驱动）；bundle 只产生候选线索，
    仍需 ScoreEngine + EvidenceGate + 人工审核。
    """

    __tablename__ = "signal_bundles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("bnd"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    bundle_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    signal_ids_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    signal_types_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 组合指向的 Pain 分类（可解释：为什么这些信号组合指向这个痛点）
    pain_categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_window_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    # 时间密度（真实历史计数，不猜）
    signal_count_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_count_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_count_90d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    explanation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    first_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship()
