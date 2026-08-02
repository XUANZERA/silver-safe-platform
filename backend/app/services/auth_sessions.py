import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.security import AuthSession
from app.models.user import User


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _format_refresh_token(session_id: str, secret: str) -> str:
    return f"{session_id}.{secret}"


def _parse_refresh_token(token: str) -> tuple[str, str]:
    session_id, separator, secret = token.partition(".")
    if not separator or len(session_id) != 36 or len(secret) < 32:
        raise AppError(401, "刷新令牌无效", "INVALID_REFRESH_TOKEN")
    return session_id, secret


def create_auth_session(db: Session, user: User) -> tuple[AuthSession, str]:
    settings = get_settings()
    session_id = str(uuid4())
    secret = secrets.token_urlsafe(48)
    auth_session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=_hash_secret(secret),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(auth_session)
    db.flush()
    return auth_session, _format_refresh_token(session_id, secret)


def get_active_auth_session(
    db: Session,
    *,
    session_id: str,
    user_id: int,
) -> AuthSession:
    auth_session = db.get(AuthSession, session_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= datetime.now(UTC)
    ):
        raise AppError(401, "登录会话已失效", "SESSION_REVOKED")
    return auth_session


def rotate_refresh_token(
    db: Session,
    token: str,
) -> tuple[AuthSession, User, str]:
    session_id, secret = _parse_refresh_token(token)
    auth_session = db.get(AuthSession, session_id)
    now = datetime.now(UTC)
    if auth_session is None:
        raise AppError(401, "刷新令牌无效", "INVALID_REFRESH_TOKEN")
    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise AppError(401, "登录会话已失效", "SESSION_REVOKED")

    supplied_hash = _hash_secret(secret)
    if not hmac.compare_digest(supplied_hash, auth_session.refresh_token_hash):
        auth_session.revoked_at = now
        db.commit()
        raise AppError(
            401,
            "检测到刷新令牌重复使用，会话已撤销",
            "REFRESH_TOKEN_REUSED",
        )

    new_secret = secrets.token_urlsafe(48)
    auth_session.refresh_token_hash = _hash_secret(new_secret)
    auth_session.last_used_at = now
    user = db.get(User, auth_session.user_id)
    if user is None:
        auth_session.revoked_at = now
        db.commit()
        raise AppError(401, "登录用户不存在", "INVALID_REFRESH_TOKEN")
    db.flush()
    return auth_session, user, _format_refresh_token(session_id, new_secret)


def revoke_auth_session(
    db: Session,
    *,
    token: str,
    user_id: int,
) -> AuthSession:
    session_id, secret = _parse_refresh_token(token)
    auth_session = db.get(AuthSession, session_id)
    if auth_session is None or auth_session.user_id != user_id:
        raise AppError(401, "刷新令牌无效", "INVALID_REFRESH_TOKEN")
    if not hmac.compare_digest(
        _hash_secret(secret),
        auth_session.refresh_token_hash,
    ):
        raise AppError(401, "刷新令牌无效", "INVALID_REFRESH_TOKEN")
    if auth_session.revoked_at is None:
        auth_session.revoked_at = datetime.now(UTC)
    return auth_session
