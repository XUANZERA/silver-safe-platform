import logging
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.alert import Alert
from app.schemas.alert import (
    AlertDetailResponse,
    AlertListResponse,
    AlertResponse,
    AlertStatus,
    AlertType,
    PaginatedAlertResponse,
    ResolveAlertRequest,
    SosRequest,
)
from app.schemas.common import ApiResponse
from app.services.access import ensure_elder_access, require_operator
from app.services.alerts import (
    ALERT_LOAD_OPTIONS,
    accept_alert,
    alert_detail_to_response,
    alert_to_response,
    get_accessible_alert_or_404,
    get_alert_or_404,
    resolve_alert,
)
from app.services.audit import add_audit_log, client_ip, has_recent_audit_event
from app.services.sos import request_sos

logger = logging.getLogger(__name__)
router = APIRouter()


def _audit_alert_read(
    db: DbSession,
    *,
    request: Request,
    current_user: CurrentUser,
    action: str,
    resource_type: str,
    resource_id: int | str,
) -> None:
    settings = get_settings()
    resource_key = str(resource_id)
    recently_recorded = has_recent_audit_event(
        db,
        action=action,
        outcome="success",
        actor_user_id=current_user.id,
        resource_type=resource_type,
        resource_id=resource_key,
        window_seconds=settings.alert_read_audit_window_seconds,
    )
    if not recently_recorded:
        add_audit_log(
            db,
            action=action,
            outcome="success",
            actor_user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_key,
            ip_address=client_ip(request),
        )
        db.commit()


@router.post(
    "/alerts/sos",
    status_code=201,
    response_model=ApiResponse[AlertResponse],
)
def create_sos(
    payload: SosRequest,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertResponse]:
    alert, created = request_sos(
        db,
        current_user=current_user,
        trip_id=payload.trip_id,
        ip_address=client_ip(request),
    )
    response.status_code = 201 if created else 200
    log = logger.warning if created else logger.info
    log(
        "sos_requested alert_id=%s elder_id=%s created=%s",
        alert.id,
        alert.elder_id,
        created,
    )
    return ApiResponse(
        data=alert_to_response(alert),
        message="求助已发送" if created else "求助已发送，请勿重复提交",
    )


@router.get(
    "/elders/{elder_id}/alerts",
    response_model=ApiResponse[AlertListResponse],
)
def list_elder_alerts(
    elder_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    status: Annotated[AlertStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[AlertListResponse]:
    ensure_elder_access(db, current_user, elder_id)
    filters = [Alert.elder_id == elder_id]
    if status is not None:
        filters.append(Alert.status == status.value)
    total = db.scalar(select(func.count(Alert.id)).where(*filters)) or 0
    alerts = list(
        db.scalars(
            select(Alert)
            .options(*ALERT_LOAD_OPTIONS)
            .where(*filters)
            .order_by(Alert.occurred_at.desc(), Alert.id.desc())
            .limit(limit)
        ).all()
    )
    _audit_alert_read(
        db,
        request=request,
        current_user=current_user,
        action="alert.list.read",
        resource_type="elder",
        resource_id=elder_id,
    )
    return ApiResponse(
        data=AlertListResponse(
            items=[alert_to_response(alert) for alert in alerts],
            total=total,
        )
    )


@router.get("/alerts", response_model=ApiResponse[PaginatedAlertResponse])
def list_alerts(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    status: Annotated[AlertStatus | None, Query()] = None,
    alert_type: Annotated[AlertType | None, Query(alias="type")] = None,
    elder_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[PaginatedAlertResponse]:
    require_operator(current_user)
    filters = []
    if status is not None:
        filters.append(Alert.status == status.value)
    if alert_type is not None:
        filters.append(Alert.type == alert_type.value)
    if elder_id is not None:
        filters.append(Alert.elder_id == elder_id)

    total = db.scalar(select(func.count(Alert.id)).where(*filters)) or 0
    alerts = list(
        db.scalars(
            select(Alert)
            .options(*ALERT_LOAD_OPTIONS)
            .where(*filters)
            .order_by(Alert.occurred_at.desc(), Alert.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    _audit_alert_read(
        db,
        request=request,
        current_user=current_user,
        action="alert.queue.read",
        resource_type="alert_queue",
        resource_id=elder_id or "all",
    )
    return ApiResponse(
        data=PaginatedAlertResponse(
            items=[alert_to_response(alert) for alert in alerts],
            page=page,
            page_size=page_size,
            total=total,
            has_more=page * page_size < total,
        )
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=ApiResponse[AlertDetailResponse],
)
def get_alert(
    alert_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertDetailResponse]:
    alert = get_accessible_alert_or_404(
        db,
        alert_id=alert_id,
        viewer=current_user,
        include_logs=True,
    )
    _audit_alert_read(
        db,
        request=request,
        current_user=current_user,
        action="alert.detail.read",
        resource_type="alert",
        resource_id=alert.id,
    )
    return ApiResponse(data=alert_detail_to_response(alert))


@router.patch(
    "/alerts/{alert_id}/accept",
    response_model=ApiResponse[AlertResponse],
)
def accept_alert_route(
    alert_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertResponse]:
    require_operator(current_user)
    alert, changed = accept_alert(db, get_alert_or_404(db, alert_id), current_user)
    logger.info(
        "alert_accept_processed alert_id=%s operator_id=%s changed=%s",
        alert.id,
        current_user.id,
        changed,
    )
    return ApiResponse(
        data=alert_to_response(alert),
        message="事件接单成功" if changed else "事件已由你接单",
    )


@router.patch(
    "/alerts/{alert_id}/resolve",
    response_model=ApiResponse[AlertResponse],
)
def resolve_alert_route(
    alert_id: int,
    payload: ResolveAlertRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertResponse]:
    require_operator(current_user)
    alert, changed = resolve_alert(
        db,
        get_alert_or_404(db, alert_id),
        current_user,
        payload.resolution,
    )
    logger.info(
        "alert_resolve_processed alert_id=%s operator_id=%s changed=%s",
        alert.id,
        current_user.id,
        changed,
    )
    return ApiResponse(
        data=alert_to_response(alert),
        message="事件处置完成" if changed else "事件已完成处置",
    )
