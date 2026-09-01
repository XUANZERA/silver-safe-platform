"""Pydantic request and response schemas."""

from app.schemas.alert import AlertResponse, AlertStatus, AlertType, SosRequest
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    UserRole,
)
from app.schemas.common import ApiResponse
from app.schemas.elder import ElderListResponse, ElderResponse, GeofenceResponse
from app.schemas.location import (
    LocationCreateRequest,
    LocationResponse,
    LocationSource,
)
from app.schemas.trip import TripCancelRequest, TripCreateRequest, TripResponse, TripStatus

__all__ = [
    "ApiResponse",
    "AlertResponse",
    "AlertStatus",
    "AlertType",
    "ElderListResponse",
    "ElderResponse",
    "GeofenceResponse",
    "LoginRequest",
    "LoginResponse",
    "LocationCreateRequest",
    "LocationResponse",
    "LocationSource",
    "SosRequest",
    "TripCancelRequest",
    "TripCreateRequest",
    "TripResponse",
    "TripStatus",
    "UserResponse",
    "UserRole",
]
