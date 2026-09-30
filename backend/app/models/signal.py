from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_id, TimestampMixin, utcnow


class Signal(TimestampMixin, Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sig"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"), index=True)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("source_records.id", ondelete="CASCADE"), index=True)
    signal_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    reliability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    heat_score: Mapped[float | None] = mapped_column(Float)
    # 生命周期：CANDIDATE→REVIEW→APPROVED/REJECTED；STALE/INVALID 失效（保留历史）；VALID 为历史兼容值
    status: Mapped[str] = mapped_column(String(30), default="REVIEW", nullable=False, index=True)
    fact_or_inference: Mapped[str] = mapped_column(String(20), default="FACT", nullable=False)
    # T04：事实与推断严格分离（fact 只能基于原文；inference 为 AI 解释，不得反向成为证据）
    fact_summary: Mapped[str | None] = mapped_column(Text)
    inference_summary: Mapped[str | None] = mapped_column(Text)
    # T04：去重指纹（company_id+type+核心事件+日期窗口 hash）；多来源合并依据
    signal_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # T04：产生来源与 Prompt 版本（可追溯由哪个分析器版本产出）
    created_by: Mapped[str] = mapped_column(String(20), default="RULE", nullable=False)  # RULE / LLM / USER / MERGE
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    # T04：变化类信号（来自真实版本比较；change_value 必须来自版本差异，不猜）
    change_type: Mapped[str | None] = mapped_column(String(30))  # NEW / INCREASE / DECREASE / REMOVED
    change_value: Mapped[str | None] = mapped_column(String(200))
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", server_default="UNVERIFIED", nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="signals")
    market: Mapped["Market | None"] = relationship(back_populates="signals")
    source_record: Mapped["SourceRecord"] = relationship(back_populates="signals")
    evidences: Mapped[list["SignalEvidence"]] = relationship(back_populates="signal", cascade="all, delete-orphan")


class SignalCandidate(TimestampMixin, Base):
    """信号候选：Rule/LLM 识别的待确认事件 —— 关键词命中≠事实，需 Evidence 校验与（自动或人工）审核。

    状态机：DETECTED → APPROVED（自动/人工，已生成正式 Signal）；REVIEW_REQUIRED → 人工；REJECTED / MERGED（并入既有 Signal）
    """

    __tablename__ = "signal_candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cand"))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("source_records.id", ondelete="CASCADE"), index=True)
    candidate_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    evidence_text: Mapped[str | None] = mapped_column(Text)  # 原文片段（必须可在原文中找到）
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    rule_confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_confidence: Mapped[int | None] = mapped_column(Integer)
    final_confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    # DETECTED / REVIEW_REQUIRED / APPROVED / REJECTED / MERGED
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)  # 生成/拒绝/合并原因（可解释）
    # 结构化事实抽取（原文明确存在才填，缺失 null —— 禁止 AI 补数字）
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    fact_summary: Mapped[str | None] = mapped_column(Text)
    inference_summary: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    # 审核后生成的正式 Signal
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id", ondelete="SET NULL"), index=True)


class SignalEvidence(TimestampMixin, Base):
    """Signal 证据：原文精确引用（quoted_text 必须来自真实原文，带 offset 可高亮）。
    多来源合并 = 同一 Signal 挂多条来自不同 SourceRecord 的 Evidence（增强 Evidence Score）。
    """

    __tablename__ = "signal_evidences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sev"))
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), index=True)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("source_records.id", ondelete="CASCADE"), index=True)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    evidence_type: Mapped[str] = mapped_column(String(30), default="ORIGINAL_TEXT", nullable=False)  # 仅原文引用；AI 推断不得作为 Evidence
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", nullable=False)

    signal: Mapped[Signal] = relationship(back_populates="evidences")
