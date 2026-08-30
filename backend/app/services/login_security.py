import hashlib
import hmac
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.audit import add_audit_log, count_recent_audit_events

LOGIN_ACTION = "auth.login"
LOGIN_SUBJECT = "login_subject"
_LOGIN_LOCKS = tuple(Lock() for _ in range(64))


def login_subject_id(username: str) -> str:
    normalized = username.strip().casefold().encode("utf-8")
    secret = get_settings().secret_key.encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()


@contextmanager
def login_attempt_guard(subject_id: str, ip_address: str | None) -> Iterator[None]:
    keys = {subject_id}
    if ip_address:
        keys.add(ip_address)
    lock_indexes = sorted(
        int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") % len(_LOGIN_LOCKS)
        for key in keys
    )
    locks = [_LOGIN_LOCKS[index] for index in dict.fromkeys(lock_indexes)]
    for lock in locks:
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()


def enforce_login_rate_limit(
    db: Session,
    *,
    subject_id: str,
    ip_address: str | None,
) -> None:
    settings = get_settings()
    subject_failures = count_recent_audit_events(
        db,
        action=LOGIN_ACTION,
        outcome="failure",
        window_seconds=settings.login_failure_window_seconds,
        resource_type=LOGIN_SUBJECT,
        resource_id=subject_id,
    )
    ip_failures = (
        count_recent_audit_events(
            db,
            action=LOGIN_ACTION,
            outcome="failure",
            window_seconds=settings.login_failure_window_seconds,
            ip_address=ip_address,
        )
        if ip_address
        else 0
    )
    if (
        subject_failures >= settings.login_failure_per_username
        or ip_failures >= settings.login_failure_per_ip
    ):
        add_audit_log(
            db,
            action=LOGIN_ACTION,
            outcome="blocked",
            resource_type=LOGIN_SUBJECT,
            resource_id=subject_id,
            ip_address=ip_address,
            details={
                "subject_failures": subject_failures,
                "ip_failures": ip_failures,
                "window_seconds": settings.login_failure_window_seconds,
            },
        )
        db.commit()
        raise AppError(429, "登录尝试过于频繁，请稍后再试", "LOGIN_RATE_LIMITED")


def record_login_failure(
    db: Session,
    *,
    subject_id: str,
    ip_address: str | None,
) -> None:
    add_audit_log(
        db,
        action=LOGIN_ACTION,
        outcome="failure",
        resource_type=LOGIN_SUBJECT,
        resource_id=subject_id,
        ip_address=ip_address,
    )
