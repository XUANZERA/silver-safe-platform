from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.security import AuditLog, AuthSession


def prune_expired_security_data(db: Session) -> None:
    now = datetime.now(UTC)
    audit_cutoff = now - timedelta(days=get_settings().audit_retention_days)
    revoked_session_cutoff = now - timedelta(days=30)

    db.execute(delete(AuditLog).where(AuditLog.occurred_at < audit_cutoff))
    db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.expires_at < now,
                AuthSession.revoked_at < revoked_session_cutoff,
            )
        )
    )
    db.commit()
