from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TripStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TripCreateRequest(BaseModel):
    destination: str = Field(min_length=1, max_length=200)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("目的地不能为空")
        return clean


class TripCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("取消原因不能为空")
        return clean


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    elder_id: int
    destination: str
    status: TripStatus
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
