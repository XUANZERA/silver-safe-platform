"""SQLAlchemy model registry."""

from app.models.alert import Alert, AlertLog
from app.models.elder import Elder, ElderFamilyBinding
from app.models.geofence import Geofence
from app.models.location import Location
from app.models.security import AuditLog, AuthSession
from app.models.trip import Trip
from app.models.user import User

__all__ = [
    "AuditLog",
    "Alert",
    "AlertLog",
    "AuthSession",
    "Elder",
    "ElderFamilyBinding",
    "Geofence",
    "Location",
    "Trip",
    "User",
]
