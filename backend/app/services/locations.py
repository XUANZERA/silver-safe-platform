from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.alert import Alert
from app.models.location import Location
from app.models.trip import Trip
from app.schemas.location import LocationCreateRequest, LocationSource
from app.services.risk import evaluate_location_risk


def _same_location(existing: Location, payload: LocationCreateRequest) -> bool:
    return (
        existing.latitude == payload.latitude
        and existing.longitude == payload.longitude
        and existing.speed_mps == payload.speed_mps
        and existing.accuracy_meters == payload.accuracy_meters
        and existing.source == payload.source.value
        and existing.recorded_at == payload.recorded_at.astimezone(UTC)
    )


def _existing_location(
    db: Session,
    *,
    trip_id: int,
    client_location_id: str,
) -> Location | None:
    return db.scalar(
        select(Location).where(
            Location.trip_id == trip_id,
            Location.client_location_id == client_location_id,
        )
    )


def _lock_active_trip(db: Session, trip_id: int) -> None:
    result = db.execute(
        update(Trip)
        .where(Trip.id == trip_id, Trip.status == "active")
        .values(id=Trip.id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError(409, "当前出游任务未进行", "TRIP_NOT_ACTIVE")


def _enforce_upload_rate_limit(db: Session, trip_id: int) -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.location_upload_window_seconds)
    count = (
        db.scalar(
            select(func.count(Location.id)).where(
                Location.trip_id == trip_id,
                Location.received_at >= cutoff,
            )
        )
        or 0
    )
    if count >= settings.location_upload_per_trip:
        db.rollback()
        raise AppError(
            429,
            "定位上传过于频繁，请稍后重试",
            "LOCATION_RATE_LIMITED",
            headers={"Retry-After": str(settings.location_upload_window_seconds)},
        )


def record_location(
    db: Session,
    *,
    trip: Trip,
    payload: LocationCreateRequest,
) -> tuple[Location, list[Alert], bool]:
    settings = get_settings()
    if payload.recorded_at.tzinfo is None:
        raise AppError(400, "recorded_at 必须包含时区", "TIMEZONE_REQUIRED")
    if settings.app_env.lower() == "production" and payload.source == LocationSource.SIMULATION:
        raise AppError(
            403,
            "生产环境不接受模拟定位",
            "SIMULATION_NOT_ALLOWED",
        )

    recorded_at = payload.recorded_at.astimezone(UTC)
    now = datetime.now(UTC)
    allowed_skew = timedelta(seconds=settings.location_clock_skew_seconds)
    if recorded_at > now + allowed_skew:
        raise AppError(400, "定位时间晚于允许范围", "INVALID_RECORDED_AT")
    if trip.started_at is not None and recorded_at < trip.started_at - allowed_skew:
        raise AppError(400, "定位时间早于出游开始时间", "INVALID_RECORDED_AT")

    _lock_active_trip(db, trip.id)
    existing = _existing_location(
        db,
        trip_id=trip.id,
        client_location_id=payload.client_location_id,
    )
    if existing is not None:
        if _same_location(existing, payload):
            db.rollback()
            return existing, [], False
        db.rollback()
        raise AppError(
            409,
            "client_location_id 已被其他定位点使用",
            "LOCATION_ID_CONFLICT",
        )

    _enforce_upload_rate_limit(db, trip.id)
    location = Location(
        trip=trip,
        client_location_id=payload.client_location_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_mps=payload.speed_mps,
        accuracy_meters=payload.accuracy_meters,
        source=payload.source.value,
        recorded_at=recorded_at,
    )
    db.add(location)
    try:
        db.flush()
        generated_events = evaluate_location_risk(db, location)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_location(
            db,
            trip_id=trip.id,
            client_location_id=payload.client_location_id,
        )
        if existing is not None and _same_location(existing, payload):
            return existing, [], False
        if existing is not None:
            raise AppError(
                409,
                "client_location_id 已被其他定位点使用",
                "LOCATION_ID_CONFLICT",
            ) from None
        raise

    db.refresh(location)
    return location, generated_events, True


def get_latest_trip_location(db: Session, trip_id: int) -> Location | None:
    return db.scalar(
        select(Location)
        .where(Location.trip_id == trip_id)
        .order_by(Location.recorded_at.desc(), Location.id.desc())
        .limit(1)
    )


def list_trip_locations(
    db: Session,
    *,
    trip_id: int,
    limit: int,
    from_time: datetime | None,
    to_time: datetime | None,
) -> tuple[list[Location], bool]:
    filters = [Location.trip_id == trip_id]
    for name, value in (("from_time", from_time), ("to_time", to_time)):
        if value is not None and value.tzinfo is None:
            raise AppError(400, f"{name} 必须包含时区", "TIMEZONE_REQUIRED")
    if from_time is not None:
        filters.append(Location.recorded_at >= from_time.astimezone(UTC))
    if to_time is not None:
        filters.append(Location.recorded_at <= to_time.astimezone(UTC))
    if from_time is not None and to_time is not None and from_time > to_time:
        raise AppError(400, "from_time 不能晚于 to_time", "INVALID_TIME_RANGE")

    newest_first = list(
        db.scalars(
            select(Location)
            .where(*filters)
            .order_by(Location.recorded_at.desc(), Location.id.desc())
            .limit(limit + 1)
        ).all()
    )
    has_more = len(newest_first) > limit
    return list(reversed(newest_first[:limit])), has_more
