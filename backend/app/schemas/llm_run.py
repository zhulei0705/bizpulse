from datetime import datetime
from decimal import Decimal

from app.schemas.common import ORMModel


class LLMRunRead(ORMModel):
    id: str
    module: str
    target_type: str | None
    target_id: str | None
    prompt_name: str | None
    prompt_version: str | None
    model: str | None
    provider: str | None
    tokens_input: int | None
    tokens_output: int | None
    cost_amount: Decimal | None
    duration_seconds: float | None
    status: str
    error_message: str | None
    created_at: datetime
