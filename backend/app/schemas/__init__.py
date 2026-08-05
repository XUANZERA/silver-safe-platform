"""Pydantic request and response schemas."""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    UserRole,
)
from app.schemas.common import ApiResponse
from app.schemas.elder import ElderListResponse, ElderResponse, GeofenceResponse
from app.schemas.trip import TripCancelRequest, TripCreateRequest, TripResponse, TripStatus

__all__ = [
    "ApiResponse",
    "ElderListResponse",
    "ElderResponse",
    "GeofenceResponse",
    "LoginRequest",
    "LoginResponse",
    "TripCancelRequest",
    "TripCreateRequest",
    "TripResponse",
    "TripStatus",
    "UserResponse",
    "UserRole",
]
