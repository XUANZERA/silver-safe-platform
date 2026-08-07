import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.common import ApiResponse
from app.schemas.location import (
    GeofenceEventResponse,
    LatestLocationResponse,
    LocationCreateRequest,
    LocationResponse,
    LocationUploadResponse,
    TrackPointResponse,
    TrackResponse,
)
from app.services.access import ensure_elder_access, get_owned_elder
from app.services.audit import add_audit_log, client_ip, count_recent_audit_events
from app.services.locations import (
    get_latest_trip_location,
    list_trip_locations,
    record_location,
)
from app.services.trips import get_trip_or_404

logger = logging.getLogger(__name__)
router = APIRouter()


def _set_private_location_headers(response: Response) -> None:
    # SecurityHeadersMiddleware adds Cache-Control: no-store to every API response.
    response.headers["Pragma"] = "no-cache"


def _audit_location_read(
    db: DbSession,
    *,
    request: Request,
    current_user: CurrentUser,
    trip_id: int,
    action: str,
) -> None:
    settings = get_settings()
    recently_recorded = count_recent_audit_events(
        db,
        action=action,
        outcome="success",
        actor_user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        window_seconds=settings.location_read_audit_window_seconds,
    )
    if recently_recorded == 0:
        add_audit_log(
            db,
            action=action,
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="trip",
            resource_id=trip_id,
            ip_address=client_ip(request),
        )
        db.commit()


@router.post(
    "/trips/{trip_id}/locations",
    status_code=201,
    response_model=ApiResponse[LocationUploadResponse],
)
def upload_location(
    trip_id: int,
    payload: LocationCreateRequest,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[LocationUploadResponse]:
    elder = get_owned_elder(db, current_user)
    trip = get_trip_or_404(db, trip_id)
    if trip.elder_id != elder.id:
        raise AppError(403, "无权为该出游上传定位", "TRIP_ACCESS_DENIED")

    location, generated_events, created = record_location(db, trip=trip, payload=payload)
    if not created:
        response.status_code = 200
    _set_private_location_headers(response)

    logger.info(
        "location_saved location_id=%s elder_id=%s trip_id=%s source=%s created=%s",
        location.id,
        trip.elder_id,
        location.trip_id,
        location.source,
        created,
    )
    return ApiResponse(
        data=LocationUploadResponse(
            **LocationResponse.model_validate(location).model_dump(),
            created=created,
            events_created=[
                GeofenceEventResponse(id=event.id, type=event.type) for event in generated_events
            ],
        ),
        message="定位保存成功" if created else "定位已保存，无需重复上传",
    )


@router.get(
    "/trips/{trip_id}/locations/latest",
    response_model=ApiResponse[LatestLocationResponse],
)
def get_latest_location(
    trip_id: int,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[LatestLocationResponse]:
    trip = get_trip_or_404(db, trip_id)
    ensure_elder_access(db, current_user, trip.elder_id)
    location = get_latest_trip_location(db, trip_id)
    _audit_location_read(
        db,
        request=request,
        current_user=current_user,
        trip_id=trip_id,
        action="location.latest.read",
    )
    _set_private_location_headers(response)
    return ApiResponse(
        data=LatestLocationResponse(
            location=LocationResponse.model_validate(location) if location else None
        ),
        message="暂无定位数据" if location is None else "操作成功",
    )


@router.get(
    "/trips/{trip_id}/locations",
    response_model=ApiResponse[TrackResponse],
)
def get_trip_locations(
    trip_id: int,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    from_time: Annotated[datetime | None, Query()] = None,
    to_time: Annotated[datetime | None, Query()] = None,
) -> ApiResponse[TrackResponse]:
    trip = get_trip_or_404(db, trip_id)
    ensure_elder_access(db, current_user, trip.elder_id)
    locations, has_more = list_trip_locations(
        db,
        trip_id=trip_id,
        limit=limit,
        from_time=from_time,
        to_time=to_time,
    )
    _audit_location_read(
        db,
        request=request,
        current_user=current_user,
        trip_id=trip_id,
        action="location.track.read",
    )
    _set_private_location_headers(response)
    return ApiResponse(
        data=TrackResponse(
            trip_id=trip_id,
            items=[TrackPointResponse.model_validate(item) for item in locations],
            total=len(locations),
            has_more=has_more,
        )
    )
