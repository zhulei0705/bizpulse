from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_id


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("aud"))
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="local-user", nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
