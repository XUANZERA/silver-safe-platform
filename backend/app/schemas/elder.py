from pydantic import BaseModel, ConfigDict, Field

from app.core.coordinates import CoordinateReferenceSystem


class ElderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    age: int | None
    health_info: str | None


class ElderListResponse(BaseModel):
    items: list[ElderResponse]
    total: int


class GeofenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    elder_id: int
    center_latitude: float
    center_longitude: float
    radius_meters: int
    enabled: bool
    crs: CoordinateReferenceSystem | None = None


class GeofenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius_meters: int = Field(ge=50, le=5000)
    enabled: bool
