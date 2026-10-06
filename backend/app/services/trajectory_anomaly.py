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
from app.ml.trajectory_anomaly.windows import (
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
    latest_window,
    sliding_windows,
)
from app.models.location import Location
from app.schemas.trajectory import TrajectoryAttentionResponse, TrajectoryAttentionStatus
from app.services.trajectory_temporal import (
    POLICY_REQUIREMENTS,
    SELECTED_TEMPORAL_POLICY,
    apply_temporal_policy,
)

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
    windows = list(
        sliding_windows(
            points,
            window_seconds=WINDOW_SECONDS,
            step_seconds=WINDOW_STEP_SECONDS,
        )
    )
    required_history, _ = POLICY_REQUIREMENTS[SELECTED_TEMPORAL_POLICY]
    if not windows:
        latest = latest_window(points)
        quality = assess_quality(
            latest.points,
            point_limit_exceeded=(
                point_limit_exceeded or len(latest.points) > MAX_TRAJECTORY_POINTS
            ),
        )
        if not latest.complete:
            reasons = tuple(dict.fromkeys((*quality.reason_codes, "INCOMPLETE_WINDOW")))
            quality = replace(quality, valid=False, reason_codes=reasons)
        return unknown_result(quality.reason_codes, point_count=len(latest.points))

    recent_windows = windows[-required_history:]
    latest_points = recent_windows[-1].points
    latest_quality = assess_quality(
        latest_points,
        point_limit_exceeded=(
            point_limit_exceeded or len(latest_points) > MAX_TRAJECTORY_POINTS
        ),
    )
    if not latest_quality.valid:
        return unknown_result(
            latest_quality.reason_codes,
            point_count=len(latest_points),
        )
    if len(recent_windows) < required_history:
        return unknown_result(
            ("TEMPORAL_HISTORY_INSUFFICIENT",),
            point_count=len(latest_points),
        )

    try:
        bundle = _cached_model_bundle()
        predictions = [
            infer_trajectory(
                window.points,
                bundle,
                point_limit_exceeded=(len(window.points) > MAX_TRAJECTORY_POINTS),
            )
            for window in recent_windows
        ]
    except TrajectoryModelError as error:
        logger.warning(
            "trajectory_anomaly_model_unavailable error_type=%s",
            type(error).__name__,
        )
        return unknown_result(
            ("MODEL_UNAVAILABLE",),
            point_count=len(latest_points),
        )
    except FeatureExtractionError:
        return unknown_result(
            ("FEATURE_EXTRACTION_FAILED",),
            point_count=len(latest_points),
            model_version=str(bundle.metadata.get("model_version", "v2")),
        )
    latest_prediction = predictions[-1]
    if latest_prediction.status == TrajectoryAttentionStatus.UNKNOWN:
        return unknown_result(
            latest_prediction.reason_codes,
            point_count=len(latest_points),
            model_version=latest_prediction.model_version,
        )
    window_alerts = [
        True
        if prediction.status == TrajectoryAttentionStatus.ATTENTION
        else False
        if prediction.status == TrajectoryAttentionStatus.NORMAL
        else None
        for prediction in predictions
    ]
    product_decision = apply_temporal_policy(
        window_alerts,
        SELECTED_TEMPORAL_POLICY,
    )[-1]
    if product_decision is None:
        return unknown_result(
            ("TEMPORAL_HISTORY_INSUFFICIENT",),
            point_count=len(latest_points),
            model_version=latest_prediction.model_version,
        )
    reason_codes = tuple(
        dict.fromkeys(
            reason
            for prediction in predictions
            if prediction.status == TrajectoryAttentionStatus.ATTENTION
            for reason in prediction.reason_codes
        )
    ) if product_decision else ()
    return TrajectoryAttentionResponse(
        status=(
            TrajectoryAttentionStatus.ATTENTION
            if product_decision
            else TrajectoryAttentionStatus.NORMAL
        ),
        score=latest_prediction.score,
        reason_codes=list(reason_codes),
        model_version=latest_prediction.model_version,
        point_count=len(latest_points),
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
