from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit(
    db: Session,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
    actor: str = "local-user",
) -> None:
    db.add(AuditLog(action=action, entity_type=entity_type, entity_id=entity_id, payload_json=payload or {}, actor=actor))
