import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.services.audit import add_audit_log, client_ip
from app.services.auth_sessions import (
    create_auth_session,
    revoke_auth_session,
    rotate_refresh_token,
)
from app.services.login_security import (
    enforce_login_rate_limit,
    login_attempt_guard,
    login_subject_id,
    record_login_failure,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")


def _login_response(
    *,
    user: User,
    session_id: str,
) -> LoginResponse:
    settings = get_settings()
    return LoginResponse(
        access_token=create_access_token(user.id, user.role, session_id),
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 86400,
        user=UserResponse.model_validate(user),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.refresh_cookie_name,
        path="/",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path=f"{settings.api_prefix}/auth",
    )


def _get_refresh_cookie(request: Request) -> str:
    token = request.cookies.get(get_settings().refresh_cookie_name)
    if not token:
        raise AppError(401, "缺少刷新令牌", "INVALID_REFRESH_TOKEN")
    return token


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> ApiResponse[LoginResponse]:
    ip_address = client_ip(request)
    subject_id = login_subject_id(payload.username)
    with login_attempt_guard(subject_id, ip_address):
        enforce_login_rate_limit(
            db,
            subject_id=subject_id,
            ip_address=ip_address,
        )
        user = db.scalar(select(User).where(User.username == payload.username))
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        password_matches = verify_password(payload.password, password_hash)
        if user is None or not password_matches:
            record_login_failure(
                db,
                subject_id=subject_id,
                ip_address=ip_address,
            )
            db.commit()
            logger.warning("login_failed subject_id=%s", subject_id)
            raise AppError(401, "用户名或密码错误", "INVALID_CREDENTIALS")

    auth_session, refresh_token = create_auth_session(db, user)
    add_audit_log(
        db,
        action="auth.login",
        outcome="success",
        actor_user_id=user.id,
        resource_type="auth_session",
        resource_id=auth_session.id,
        ip_address=ip_address,
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    logger.info("login_success user_id=%s role=%s", user.id, user.role)
    return ApiResponse(
        data=_login_response(
            user=user,
            session_id=auth_session.id,
        ),
        message="登录成功",
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: CurrentUser) -> ApiResponse[UserResponse]:
    return ApiResponse(data=UserResponse.model_validate(current_user))


@router.post("/refresh", response_model=ApiResponse[LoginResponse])
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
) -> ApiResponse[LoginResponse]:
    ip_address = client_ip(request)
    try:
        auth_session, user, refresh_token = rotate_refresh_token(
            db,
            _get_refresh_cookie(request),
        )
    except AppError as exc:
        add_audit_log(
            db,
            action="auth.refresh",
            outcome="failure",
            ip_address=ip_address,
            details={"error_code": exc.error_code},
        )
        db.commit()
        raise

    add_audit_log(
        db,
        action="auth.refresh",
        outcome="success",
        actor_user_id=user.id,
        resource_type="auth_session",
        resource_id=auth_session.id,
        ip_address=ip_address,
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(
        data=_login_response(
            user=user,
            session_id=auth_session.id,
        ),
        message="令牌刷新成功",
    )


@router.post("/logout", response_model=ApiResponse[None])
def logout(
    request: Request,
    response: Response,
    db: DbSession,
) -> ApiResponse[None]:
    settings = get_settings()
    token = request.cookies.get(settings.refresh_cookie_name)
    auth_session = None
    outcome = "no_token"
    error_code = None
    if token:
        try:
            auth_session = revoke_auth_session(db, token=token)
            outcome = "success"
        except AppError as exc:
            db.rollback()
            outcome = "invalid_token"
            error_code = exc.error_code

    add_audit_log(
        db,
        action="auth.logout",
        outcome=outcome,
        actor_user_id=auth_session.user_id if auth_session else None,
        resource_type="auth_session" if auth_session else None,
        resource_id=auth_session.id if auth_session else None,
        ip_address=client_ip(request),
        details={"error_code": error_code} if error_code else None,
    )
    db.commit()
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=f"{settings.api_prefix}/auth",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )
    response.delete_cookie(
        settings.refresh_cookie_name,
        path="/",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )
    return ApiResponse(data=None, message="已安全退出")
