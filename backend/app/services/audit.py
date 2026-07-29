import json

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.security import AuditLog


def client_ip(request: Request) -> str | None:
    if get_settings().app_env.lower() == "production":
        forwarded = request.headers.get("x-real-ip")
        if forwarded:
            return forwarded[:64]
    return request.client.host[:64] if request.client else None


def add_audit_log(
    db: Session,
    *,
    action: str,
    outcome: str,
    actor_user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: int | str | None = None,
    ip_address: str | None = None,
    details: dict[str, object] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip_address,
        details=json.dumps(details, ensure_ascii=False, separators=(",", ":")) if details else None,
    )
    db.add(log)
    return log
