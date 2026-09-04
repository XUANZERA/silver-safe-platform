from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import Alert
from app.models.location import Location
from app.schemas.alert import AlertResponse
from app.schemas.location import LocationResponse
from app.schemas.safety import LocationHealth, RiskStatus, SafetyViewResponse
from app.services.alerts import ALERT_LOAD_OPTIONS, alert_to_response
from app.services.locations import get_latest_trip_location
from app.services.risk import evaluate_geofence_risk
from app.services.trips import get_current_trip

OPEN_ALERT_STATUSES = ("new", "processing")


def _location_health(location: Location | None, calculated_at: datetime) -> LocationHealth:
    if location is None:
        return LocationHealth.NO_DATA

    settings = get_settings()
    age_seconds = max(0.0, (calculated_at - location.recorded_at).total_seconds())
    if age_seconds > settings.location_stale_after_seconds:
        return LocationHealth.STALE

    if (
        location.accuracy_meters is None
        or location.accuracy_meters > settings.geofence_max_accuracy_meters
    ):
        return LocationHealth.INACCURATE
    return LocationHealth.FRESH


def get_safety_view(db: Session, *, elder_id: int) -> SafetyViewResponse:
    calculated_at = datetime.now(UTC)
    trip = get_current_trip(db, elder_id)
    latest_location = None
    if trip is not None:
        latest_location = get_latest_trip_location(db, trip.id)

    location_health = _location_health(latest_location, calculated_at)
    risk_status = None
    if trip is not None and trip.status == "active" and latest_location is not None:
        evaluation = evaluate_geofence_risk(db, trip_id=trip.id, elder_id=elder_id)
        if (
            evaluation is not None
            and evaluation.latest_location_id == latest_location.id
            and location_health == LocationHealth.FRESH
        ):
            risk_status = RiskStatus(evaluation.status.value)

    open_filters = (
        Alert.elder_id == elder_id,
        Alert.status.in_(OPEN_ALERT_STATUSES),
    )
    open_alert_count = db.scalar(select(func.count(Alert.id)).where(*open_filters)) or 0
    latest_open_alert = db.scalar(
        select(Alert)
        .options(*ALERT_LOAD_OPTIONS)
        .where(*open_filters)
        .order_by(Alert.occurred_at.desc(), Alert.id.desc())
        .limit(1)
    )

    latest_location_response = (
        LocationResponse.model_validate(latest_location) if latest_location is not None else None
    )
    latest_open_alert_response: AlertResponse | None = (
        alert_to_response(latest_open_alert) if latest_open_alert is not None else None
    )
    return SafetyViewResponse(
        elder_id=elder_id,
        trip_status=trip.status if trip is not None else None,
        location_health=location_health,
        risk_status=risk_status,
        open_alert_count=open_alert_count,
        latest_location=latest_location_response,
        latest_open_alert=latest_open_alert_response,
        calculated_at=calculated_at,
    )
