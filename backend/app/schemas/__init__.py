"""Pydantic request and response schemas."""

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
    "ElderListResponse",
    "ElderResponse",
    "GeofenceResponse",
    "LoginRequest",
    "LoginResponse",
    "LocationCreateRequest",
    "LocationResponse",
    "LocationSource",
    "TripCancelRequest",
    "TripCreateRequest",
    "TripResponse",
    "TripStatus",
    "UserResponse",
    "UserRole",
]
