"""Optional trajectory anomaly feature, separate from geofence risk evaluation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.coordinates import CoordinateReferenceSystem
from app.ml.trajectory_anomaly.features import FeatureExtractionError, GpsPoint
from app.ml.trajectory_anomaly.inference import infer_trajectory
from app.ml.trajectory_anomaly.model import ModelBundle, TrajectoryModelError, load_artifact
from app.ml.trajectory_anomaly.quality import assess_quality
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS, latest_window
from app.models.location import Location
from app.schemas.trajectory import TrajectoryAttentionResponse, TrajectoryAttentionStatus

logger = logging.getLogger(__name__)
TRAJECTORY_WINDOW_SECONDS = WINDOW_SECONDS
MAX_TRAJECTORY_POINTS = 500


@lru_cache(maxsize=1)
def _cached_model_bundle() -> ModelBundle:
    return load_artifact()


def clear_cached_model_for_tests() -> None:
    _cached_model_bundle.cache_clear()


def _points_from_locations(locations: Sequence[Location]) -> list[GpsPoint]:
    return [
        GpsPoint(
            timestamp=location.recorded_at,
            latitude=location.latitude,
            longitude=location.longitude,
            accuracy_meters=location.accuracy_meters,
        )
        for location in locations
    ]


def unknown_result(
    reason_codes: Sequence[str],
    *,
    point_count: int = 0,
    model_version: str | None = None,
) -> TrajectoryAttentionResponse:
    return TrajectoryAttentionResponse(
        status=TrajectoryAttentionStatus.UNKNOWN,
        score=None,
        reason_codes=list(reason_codes),
        model_version=model_version,
        point_count=point_count,
    )


def evaluate_locations(
    locations: Sequence[Location],
    *,
    point_limit_exceeded: bool = False,
) -> TrajectoryAttentionResponse:
    points = _points_from_locations(locations)
    window = latest_window(points)
    window_points = window.points
    quality = assess_quality(
        window_points,
        point_limit_exceeded=(
            point_limit_exceeded or len(window_points) > MAX_TRAJECTORY_POINTS
        ),
    )
    if not window.complete:
        reasons = tuple(dict.fromkeys((*quality.reason_codes, "INCOMPLETE_WINDOW")))
        quality = replace(quality, valid=False, reason_codes=reasons)
    if not quality.valid:
        return unknown_result(quality.reason_codes, point_count=len(window_points))

    try:
        bundle = _cached_model_bundle()
        prediction = infer_trajectory(
            window_points,
            bundle,
            point_limit_exceeded=(len(window_points) > MAX_TRAJECTORY_POINTS),
        )
    except TrajectoryModelError as error:
        logger.warning(
            "trajectory_anomaly_model_unavailable error_type=%s",
            type(error).__name__,
        )
        return unknown_result(
            ("MODEL_UNAVAILABLE",),
            point_count=len(window_points),
        )
    except FeatureExtractionError:
        return unknown_result(
            ("FEATURE_EXTRACTION_FAILED",),
            point_count=len(window_points),
            model_version=str(bundle.metadata.get("model_version", "v2")),
        )
    return TrajectoryAttentionResponse(
        status=TrajectoryAttentionStatus(prediction.status.value),
        score=prediction.score,
        reason_codes=list(prediction.reason_codes),
        model_version=prediction.model_version,
        point_count=len(window_points),
    )


def evaluate_trip_window(db: Session, *, trip_id: int) -> TrajectoryAttentionResponse:
    newest_first = list(
        db.scalars(
            select(Location)
            .where(
                Location.trip_id == trip_id,
                Location.source_crs == CoordinateReferenceSystem.WGS84.value,
            )
            .order_by(Location.recorded_at.desc(), Location.id.desc())
            .limit(MAX_TRAJECTORY_POINTS + 1)
        ).all()
    )
    if not newest_first:
        return evaluate_locations([])
    return evaluate_locations(
        list(reversed(newest_first)),
        point_limit_exceeded=False,
    )
