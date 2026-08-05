import json
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.security import AuditLog


def client_ip(request: Request) -> str | None:
    if request.client is None:
        return None

    peer = request.client.host
    settings = get_settings()
    try:
        peer_address = ip_address(peer)
        trusted = any(
            peer_address in ip_network(network, strict=False)
            for network in settings.trusted_proxy_networks
        )
    except ValueError:
        trusted = False

    if trusted:
        forwarded = request.headers.get("x-real-ip")
        try:
            return str(ip_address(forwarded)) if forwarded else peer[:64]
        except ValueError:
            pass
    return peer[:64]


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


def count_recent_audit_events(
    db: Session,
    *,
    action: str,
    window_seconds: int,
    outcome: str | None = None,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    filters = [AuditLog.action == action, AuditLog.occurred_at >= cutoff]
    if outcome is not None:
        filters.append(AuditLog.outcome == outcome)
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if ip_address is not None:
        filters.append(AuditLog.ip_address == ip_address)
    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)
    return db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
