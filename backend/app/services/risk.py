from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import Alert
from app.models.geofence import Geofence
from app.models.location import Location

EARTH_RADIUS_METERS = 6_371_000


def distance_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Calculate prototype-scale point distance with a stable Haversine formula."""
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(min(1.0, max(0.0, haversine))))


def _has_recent_unresolved_event(db: Session, location: Location) -> bool:
    settings = get_settings()
    cutoff = location.recorded_at - timedelta(minutes=settings.geofence_alert_cooldown_minutes)
    return (
        db.scalar(
            select(Alert.id)
            .where(
                Alert.trip_id == location.trip_id,
                Alert.type == "geofence_exit",
                Alert.status.in_(("new", "processing")),
                Alert.occurred_at >= cutoff,
            )
            .limit(1)
        )
        is not None
    )


def _detect_geofence_exit(db: Session, location: Location) -> Alert | None:
    settings = get_settings()
    if (
        location.accuracy_meters is None
        or location.accuracy_meters > settings.geofence_max_accuracy_meters
    ):
        return None

    geofence = db.scalar(
        select(Geofence).where(
            Geofence.elder_id == location.trip.elder_id,
            Geofence.enabled.is_(True),
        )
    )
    if geofence is None:
        return None

    recent = list(
        db.scalars(
            select(Location)
            .where(
                Location.trip_id == location.trip_id,
                Location.accuracy_meters.is_not(None),
                Location.accuracy_meters <= settings.geofence_max_accuracy_meters,
            )
            .order_by(Location.recorded_at.desc(), Location.id.desc())
            .limit(settings.geofence_trigger_count)
        ).all()
    )
    if len(recent) < settings.geofence_trigger_count or recent[0].id != location.id:
        return None

    all_outside = all(
        distance_meters(
            item.latitude,
            item.longitude,
            geofence.center_latitude,
            geofence.center_longitude,
        )
        > geofence.radius_meters
        for item in recent
    )
    if not all_outside or _has_recent_unresolved_event(db, location):
        return None

    event = Alert(
        elder_id=location.trip.elder_id,
        trip_id=location.trip_id,
        type="geofence_exit",
        status="new",
        latitude=location.latitude,
        longitude=location.longitude,
        occurred_at=location.recorded_at,
    )
    db.add(event)
    db.flush()
    return event


def evaluate_location_risk(db: Session, location: Location) -> list[Alert]:
    event = _detect_geofence_exit(db, location)
    return [event] if event is not None else []
