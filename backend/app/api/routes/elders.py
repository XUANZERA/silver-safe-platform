from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.coordinates import CoordinateReferenceSystem
from app.core.errors import AppError
from app.models.geofence import Geofence
from app.schemas.common import ApiResponse
from app.schemas.elder import (
    ElderListResponse,
    ElderResponse,
    GeofenceResponse,
    GeofenceUpdateRequest,
)
from app.schemas.safety import LocationHealth, SafetyViewResponse
from app.services.access import ensure_elder_access, list_accessible_elders
from app.services.audit import add_audit_log, client_ip, has_recent_audit_event
from app.services.locations import get_latest_elder_location
from app.services.privacy import elder_to_response
from app.services.safety import assess_location_health, get_safety_view

router = APIRouter()


def _audit_safety_read(
    db: DbSession,
    *,
    request: Request,
    current_user: CurrentUser,
    elder_id: int,
) -> None:
    settings = get_settings()
    audit_window_seconds = min(
        settings.location_read_audit_window_seconds,
        settings.alert_read_audit_window_seconds,
    )
    recently_recorded = has_recent_audit_event(
        db,
        action="safety.read",
        outcome="success",
        actor_user_id=current_user.id,
        resource_type="elder",
        resource_id=str(elder_id),
        window_seconds=audit_window_seconds,
    )
    if not recently_recorded:
        add_audit_log(
            db,
            action="safety.read",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="elder",
            resource_id=elder_id,
            ip_address=client_ip(request),
        )
        db.commit()


@router.get("/elders", response_model=ApiResponse[ElderListResponse])
def list_elders(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ElderListResponse]:
    elders = list_accessible_elders(db, current_user)
    ip_address = client_ip(request)
    items = [
        elder_to_response(db, elder=elder, viewer=current_user, ip_address=ip_address)
        for elder in elders
    ]
    db.commit()
    return ApiResponse(data=ElderListResponse(items=items, total=len(items)))


@router.get("/elders/{elder_id}", response_model=ApiResponse[ElderResponse])
def get_elder(
    elder_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ElderResponse]:
    elder = ensure_elder_access(db, current_user, elder_id)
    response = elder_to_response(
        db,
        elder=elder,
        viewer=current_user,
        ip_address=client_ip(request),
    )
    db.commit()
    return ApiResponse(data=response)


@router.get("/elders/{elder_id}/geofence", response_model=ApiResponse[GeofenceResponse])
def get_geofence(
    elder_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[GeofenceResponse]:
    ensure_elder_access(db, current_user, elder_id)
    geofence = db.scalar(
        select(Geofence).where(
            Geofence.elder_id == elder_id,
            Geofence.crs == CoordinateReferenceSystem.WGS84.value,
        )
    )
    if geofence is None:
        return ApiResponse(data=None, message="暂未配置安全围栏")
    return ApiResponse(data=GeofenceResponse.model_validate(geofence))


@router.put(
    "/elders/{elder_id}/geofence",
    response_model=ApiResponse[GeofenceResponse],
)
def update_geofence(
    elder_id: int,
    payload: GeofenceUpdateRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[GeofenceResponse]:
    if current_user.role != "family":
        raise AppError(403, "仅家属账号可配置安全围栏", "FAMILY_ROLE_REQUIRED")

    ensure_elder_access(db, current_user, elder_id)
    geofence = db.get(Geofence, elder_id)
    if not payload.enabled:
        if geofence is None:
            raise AppError(409, "尚未配置安全围栏", "GEOFENCE_NOT_CONFIGURED")
        geofence.radius_meters = payload.radius_meters
        geofence.enabled = False
    else:
        latest_location = get_latest_elder_location(db, elder_id)
        health = assess_location_health(latest_location, datetime.now(UTC))
        if health == LocationHealth.NO_DATA:
            raise AppError(409, "没有可用的 WGS84 定位", "GEOFENCE_LOCATION_NO_DATA")
        if health == LocationHealth.STALE:
            raise AppError(409, "最新定位已过期", "GEOFENCE_LOCATION_STALE")
        if health == LocationHealth.INACCURATE:
            raise AppError(422, "最新定位精度不足", "GEOFENCE_LOCATION_INACCURATE")

        assert latest_location is not None
        if geofence is None:
            geofence = Geofence(elder_id=elder_id)
            db.add(geofence)
        geofence.center_latitude = latest_location.latitude
        geofence.center_longitude = latest_location.longitude
        geofence.radius_meters = payload.radius_meters
        geofence.enabled = True
        geofence.crs = CoordinateReferenceSystem.WGS84.value

    db.flush()
    add_audit_log(
        db,
        action="geofence.configure",
        outcome="success",
        actor_user_id=current_user.id,
        resource_type="elder",
        resource_id=elder_id,
        ip_address=client_ip(request),
        details={
            "radius_meters": payload.radius_meters,
            "enabled": payload.enabled,
        },
    )
    db.commit()
    db.refresh(geofence)
    return ApiResponse(
        data=GeofenceResponse.model_validate(geofence),
        message="安全围栏配置已保存",
    )


@router.get(
    "/elders/{elder_id}/safety",
    response_model=ApiResponse[SafetyViewResponse],
)
def get_elder_safety(
    elder_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[SafetyViewResponse]:
    ensure_elder_access(db, current_user, elder_id)
    safety_view = get_safety_view(db, elder_id=elder_id)
    _audit_safety_read(
        db,
        request=request,
        current_user=current_user,
        elder_id=elder_id,
    )
    return ApiResponse(data=safety_view)
