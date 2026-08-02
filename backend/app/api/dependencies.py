from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import TokenExpiredError, decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_sessions import get_active_auth_session

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: DbSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "请先登录", "UNAUTHORIZED")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
        session_id = str(payload["sid"])
    except TokenExpiredError:
        raise AppError(401, "访问令牌已过期，请重新登录", "TOKEN_EXPIRED") from None
    except (ValueError, KeyError, TypeError):
        raise AppError(401, "登录已失效，请重新登录", "INVALID_TOKEN") from None

    user = db.get(User, user_id)
    if user is None:
        raise AppError(401, "登录用户不存在", "INVALID_TOKEN")
    get_active_auth_session(db, session_id=session_id, user_id=user_id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
