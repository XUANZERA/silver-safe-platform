from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.alert import AlertResponse
from app.schemas.location import LocationResponse
from app.schemas.trip import TripStatus


class LocationHealth(StrEnum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"
    INACCURATE = "INACCURATE"
    FRESHNESS_TBD = "FRESHNESS_TBD"


class RiskStatus(StrEnum):
    SAFE = "SAFE"
    PENDING = "PENDING"
    ALERT = "ALERT"


class SafetyViewResponse(BaseModel):
    elder_id: int
    trip_status: TripStatus | None
    location_health: LocationHealth
    risk_status: RiskStatus | None
    open_alert_count: int
    latest_location: LocationResponse | None
    latest_open_alert: AlertResponse | None
    calculated_at: datetime
