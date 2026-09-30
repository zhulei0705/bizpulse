from decimal import Decimal

from sqlalchemy import Float, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_id


class LLMRun(TimestampMixin, Base):
    __tablename__ = "llm_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("run"))
    module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    prompt_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50), index=True)
    model: Mapped[str | None] = mapped_column(String(100), index=True)
    provider: Mapped[str | None] = mapped_column(String(100))
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
