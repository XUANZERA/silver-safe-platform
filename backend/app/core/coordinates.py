from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import AppError


class CoordinateReferenceSystem(StrEnum):
    WGS84 = "WGS84"


@dataclass(frozen=True)
class CanonicalCoordinates:
    latitude: float
    longitude: float
    crs: CoordinateReferenceSystem


def normalize_location_coordinates(
    *,
    latitude: float,
    longitude: float,
    source_crs: str | CoordinateReferenceSystem,
) -> CanonicalCoordinates:
    """Validate the Phase 1 source CRS and return canonical WGS84 coordinates."""
    if source_crs != CoordinateReferenceSystem.WGS84:
        raise AppError(
            422,
            "Phase 1 仅支持 source_crs=WGS84",
            "UNSUPPORTED_SOURCE_CRS",
        )
    return CanonicalCoordinates(
        latitude=latitude,
        longitude=longitude,
        crs=CoordinateReferenceSystem.WGS84,
    )
