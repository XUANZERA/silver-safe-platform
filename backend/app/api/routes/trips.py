import logging

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.core.errors import AppError
from app.models.trip import Trip
from app.schemas.common import ApiResponse
from app.schemas.trip import TripCancelRequest, TripCreateRequest, TripResponse
from app.services.access import ensure_elder_access, get_owned_elder
from app.services.trips import cancel_trip, create_trip, end_trip, get_trip_or_404, start_trip
from app.services.trips import get_current_trip as find_current_trip

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_trip_owner(db: DbSession, current_user: CurrentUser, trip: Trip) -> None:
    elder = get_owned_elder(db, current_user)
    if trip.elder_id != elder.id:
        raise AppError(403, "无权操作该出游任务", "TRIP_ACCESS_DENIED")


@router.post("/trips", status_code=201, response_model=ApiResponse[TripResponse])
def create_trip_route(
    payload: TripCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    elder = get_owned_elder(db, current_user)
    trip = create_trip(db, elder, payload.destination)
    logger.info("trip_created trip_id=%s elder_id=%s", trip.id, elder.id)
    return ApiResponse(data=TripResponse.model_validate(trip), message="出游任务创建成功")


@router.get("/trips/{trip_id}", response_model=ApiResponse[TripResponse])
def get_trip(
    trip_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    trip = get_trip_or_404(db, trip_id)
    ensure_elder_access(db, current_user, trip.elder_id)
    return ApiResponse(data=TripResponse.model_validate(trip))


@router.post("/trips/{trip_id}/start", response_model=ApiResponse[TripResponse])
def start_trip_route(
    trip_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    trip = get_trip_or_404(db, trip_id)
    _ensure_trip_owner(db, current_user, trip)
    trip = start_trip(db, trip)
    logger.info("trip_started trip_id=%s elder_id=%s", trip.id, trip.elder_id)
    return ApiResponse(data=TripResponse.model_validate(trip), message="出游已开始")


@router.post("/trips/{trip_id}/end", response_model=ApiResponse[TripResponse])
def end_trip_route(
    trip_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    trip = get_trip_or_404(db, trip_id)
    _ensure_trip_owner(db, current_user, trip)
    trip = end_trip(db, trip)
    logger.info("trip_ended trip_id=%s elder_id=%s", trip.id, trip.elder_id)
    return ApiResponse(data=TripResponse.model_validate(trip), message="出游已结束")


@router.post("/trips/{trip_id}/cancel", response_model=ApiResponse[TripResponse])
def cancel_trip_route(
    trip_id: int,
    payload: TripCancelRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    trip = get_trip_or_404(db, trip_id)
    _ensure_trip_owner(db, current_user, trip)
    trip = cancel_trip(db, trip, payload.reason)
    logger.info("trip_cancelled trip_id=%s elder_id=%s", trip.id, trip.elder_id)
    return ApiResponse(data=TripResponse.model_validate(trip), message="出游已取消")


@router.get("/elders/{elder_id}/current-trip", response_model=ApiResponse[TripResponse])
def get_current_trip(
    elder_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TripResponse]:
    ensure_elder_access(db, current_user, elder_id)
    trip = find_current_trip(db, elder_id)
    if trip is None:
        return ApiResponse(data=None, message="当前没有未完成的出游任务")
    return ApiResponse(data=TripResponse.model_validate(trip))
