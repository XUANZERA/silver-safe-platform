import json
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
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


def _recent_audit_filters(
    *,
    action: str,
    window_seconds: int,
    outcome: str | None = None,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> list[object]:
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
    return filters


def count_recent_audit_events(db: Session, **criteria: object) -> int:
    filters = _recent_audit_filters(**criteria)
    return db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0


def has_recent_audit_event(db: Session, **criteria: object) -> bool:
    filters = _recent_audit_filters(**criteria)
    return db.scalar(select(AuditLog.id).where(*filters).limit(1)) is not None


def begin_sos_audit(
    db: Session,
    *,
    actor_user_id: int,
    ip_address: str | None,
) -> AuditLog:
    """Create and rate-check one SOS attempt inside the caller's lock."""
    settings = get_settings()
    log = add_audit_log(
        db,
        action="sos.request",
        outcome="pending",
        actor_user_id=actor_user_id,
        ip_address=ip_address,
    )
    db.flush()

    user_count = count_recent_audit_events(
        db,
        action="sos.request",
        window_seconds=settings.sos_rate_limit_window_seconds,
        actor_user_id=actor_user_id,
    )
    ip_count = (
        count_recent_audit_events(
            db,
            action="sos.request",
            window_seconds=settings.sos_rate_limit_window_seconds,
            ip_address=ip_address,
        )
        if ip_address
        else 0
    )
    if user_count > settings.sos_rate_limit_per_user or ip_count > settings.sos_rate_limit_per_ip:
        log.outcome = "blocked"
        log.details = json.dumps(
            {
                "user_count": user_count,
                "ip_count": ip_count,
                "window_seconds": settings.sos_rate_limit_window_seconds,
            },
            separators=(",", ":"),
        )
        db.commit()
        raise AppError(
            429,
            "SOS 请求过于频繁，请稍后再试",
            "SOS_RATE_LIMITED",
            headers={"Retry-After": str(settings.sos_rate_limit_window_seconds)},
        )
    return log
