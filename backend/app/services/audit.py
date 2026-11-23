from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import hash_identifier
from app.models import AuditLog


def record(
    db: Session,
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: object | None = None,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Agrega una entrada de auditoría. La transacción (commit) es responsabilidad de quien llama."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_hash=hash_identifier(ip) if ip else None,
            details=details or {},
        )
    )
