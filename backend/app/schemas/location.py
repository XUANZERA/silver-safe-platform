from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.core.coordinates import CoordinateReferenceSystem


class LocationSource(StrEnum):
    SIMULATION = "simulation"
    H5 = "h5"


class LocationCreateRequest(BaseModel):
    client_location_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_mps: float | None = Field(default=None, ge=0, le=100)
    accuracy_meters: float | None = Field(default=None, ge=0, le=10000)
    source: LocationSource = LocationSource.H5
    source_crs: CoordinateReferenceSystem
    recorded_at: datetime


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    client_location_id: str
    latitude: float
    longitude: float
    speed_mps: float | None
    accuracy_meters: float | None
    source: LocationSource
    source_crs: CoordinateReferenceSystem
    recorded_at: datetime
    received_at: datetime


class TrackPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float
    longitude: float
    accuracy_meters: float | None
    source_crs: CoordinateReferenceSystem
    recorded_at: datetime


class TrackResponse(BaseModel):
    trip_id: int
    items: list[TrackPointResponse]
    total: int
    has_more: bool


class GeofenceEventResponse(BaseModel):
    id: int
    type: str


class LocationUploadResponse(LocationResponse):
    created: bool
    events_created: list[GeofenceEventResponse]


class LatestLocationResponse(BaseModel):
    location: LocationResponse | None
