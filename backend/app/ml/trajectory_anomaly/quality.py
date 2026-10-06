"""Independent GPS quality gate. Invalid trajectories never reach Isolation Forest."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from statistics import mean, median

from app.ml.trajectory_anomaly.features import GpsPoint, haversine_meters

QUALITY_CONFIG = {
    "min_points": 20,
    "minimum_time_span_seconds": 300.0,
    "maximum_timestamp_gap_seconds": 120.0,
    "minimum_accuracy_coverage": 0.8,
    "maximum_median_accuracy_meters": 40.0,
    "maximum_mean_accuracy_meters": 50.0,
    "maximum_implied_speed_mps": 20.0,
}


@dataclass(frozen=True)
class QualityResult:
    valid: bool
    reason_codes: tuple[str, ...]
    point_count: int
    time_span_seconds: float | None
    maximum_gap_seconds: float | None
    median_accuracy_meters: float | None
    mean_accuracy_meters: float | None


def assess_quality(
    points: Sequence[GpsPoint],
    *,
    point_limit_exceeded: bool = False,
) -> QualityResult:
    reasons: list[str] = []
    count = len(points)
    span: float | None = None
    max_gap: float | None = None
    accuracy_values: list[float] = []

    if point_limit_exceeded:
        reasons.append("POINT_LIMIT_EXCEEDED")
    if count < QUALITY_CONFIG["min_points"]:
        reasons.append("TOO_FEW_POINTS")

    for point in points:
        timestamp = point.timestamp
        if (
            timestamp.tzinfo is None or timestamp.utcoffset() is None
        ) and "NAIVE_TIMESTAMP" not in reasons:
            reasons.append("NAIVE_TIMESTAMP")
        if (
            not isfinite(point.latitude) or not isfinite(point.longitude)
        ) and "NON_FINITE_COORDINATE" not in reasons:
            reasons.append("NON_FINITE_COORDINATE")
        elif (
            not -90 <= point.latitude <= 90 or not -180 <= point.longitude <= 180
        ) and "INVALID_COORDINATE" not in reasons:
            reasons.append("INVALID_COORDINATE")
        accuracy = point.accuracy_meters
        if accuracy is not None:
            if not isfinite(accuracy) or accuracy < 0:
                if "INVALID_ACCURACY" not in reasons:
                    reasons.append("INVALID_ACCURACY")
            else:
                accuracy_values.append(accuracy)

    if count >= 2 and not any(code == "NAIVE_TIMESTAMP" for code in reasons):
        durations: list[float] = []
        try:
            durations = [
                (points[index + 1].timestamp - points[index].timestamp).total_seconds()
                for index in range(count - 1)
            ]
        except TypeError:
            reasons.append("INCONSISTENT_TIMEZONES")
        if durations:
            if any(value <= 0 for value in durations):
                reasons.append("NON_MONOTONIC_TIMESTAMPS")
            else:
                max_gap = max(durations)
                if max_gap > QUALITY_CONFIG["maximum_timestamp_gap_seconds"]:
                    reasons.append("TIMESTAMP_GAP")
                span = sum(durations)
                if span < QUALITY_CONFIG["minimum_time_span_seconds"]:
                    reasons.append("SHORT_TIME_SPAN")
                if all(isfinite(point.latitude) and isfinite(point.longitude) for point in points):
                    max_speed = (
                        max(
                            haversine_meters(points[index], points[index + 1]) / duration
                            for index, duration in enumerate(durations)
                            if duration > 0
                        )
                        if any(value > 0 for value in durations)
                        else 0.0
                    )
                    if max_speed > QUALITY_CONFIG["maximum_implied_speed_mps"]:
                        reasons.append("IMPOSSIBLE_SPEED")

    coverage = len(accuracy_values) / count if count else 0.0
    if coverage < QUALITY_CONFIG["minimum_accuracy_coverage"]:
        reasons.append("INSUFFICIENT_ACCURACY_COVERAGE")
    median_accuracy = median(accuracy_values) if accuracy_values else None
    mean_accuracy = mean(accuracy_values) if accuracy_values else None
    if (
        median_accuracy is not None
        and median_accuracy > QUALITY_CONFIG["maximum_median_accuracy_meters"]
    ):
        reasons.append("POOR_MEDIAN_ACCURACY")
    if mean_accuracy is not None and mean_accuracy > QUALITY_CONFIG["maximum_mean_accuracy_meters"]:
        reasons.append("POOR_MEAN_ACCURACY")

    # Keep the reason order stable in metrics and API responses.
    ordered_reasons = tuple(dict.fromkeys(reasons))
    return QualityResult(
        valid=not ordered_reasons,
        reason_codes=ordered_reasons,
        point_count=count,
        time_span_seconds=span,
        maximum_gap_seconds=max_gap,
        median_accuracy_meters=median_accuracy,
        mean_accuracy_meters=mean_accuracy,
    )
