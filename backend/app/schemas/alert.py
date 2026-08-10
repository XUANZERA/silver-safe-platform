from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AlertType(StrEnum):
    EMERGENCY = "emergency"
    GEOFENCE_EXIT = "geofence_exit"


class AlertStatus(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    RESOLVED = "resolved"


class UserSummary(BaseModel):
    id: int
    username: str


class AlertResponse(BaseModel):
    id: int
    elder_id: int
    trip_id: int
    type: AlertType
    status: AlertStatus
    latitude: float | None
    longitude: float | None
    occurred_at: datetime
    handler: UserSummary | None
    accepted_at: datetime | None
    resolved_at: datetime | None
    resolution: str | None


class AlertLogResponse(BaseModel):
    id: int
    action: str
    operator: UserSummary
    created_at: datetime


class AlertDetailResponse(BaseModel):
    alert: AlertResponse
    logs: list[AlertLogResponse]


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int


class PaginatedAlertResponse(AlertListResponse):
    page: int
    page_size: int
    has_more: bool


class SosRequest(BaseModel):
    trip_id: int = Field(gt=0)


class ResolveAlertRequest(BaseModel):
    resolution: str = Field(min_length=2, max_length=500)

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        clean = value.strip()
        if len(clean) < 2:
            raise ValueError("处置结果至少包含 2 个有效字符")
        return clean
