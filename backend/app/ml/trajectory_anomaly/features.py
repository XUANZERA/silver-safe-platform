"""Interpretable features extracted from ordered WGS84 GPS samples."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from math import atan2, cos, degrees, isfinite, radians, sin, sqrt
from statistics import mean, median, pstdev

EARTH_RADIUS_METERS = 6_371_000.0
FEATURE_NAMES = (
    "median_speed",
    "speed_std",
    "max_speed",
    "path_length",
    "direct_distance",
    "tortuosity",
    "longest_stop_seconds",
    "stop_ratio",
    "large_turn_count",
    "mean_accuracy",
)
FEATURE_DEFINITIONS = {
    "median_speed": "Median Haversine segment distance / positive timestamp delta, in m/s.",
    "speed_std": "Population standard deviation of Haversine segment speeds, in m/s.",
    "max_speed": "Maximum Haversine segment distance / timestamp delta, in m/s.",
    "path_length": "Sum of adjacent Haversine distances, in meters.",
    "direct_distance": "Haversine distance from first to last sample, in meters.",
    "tortuosity": (
        "min(10, path_length / max(direct_distance, 10 m)); bounded for near-zero displacement."
    ),
    "longest_stop_seconds": "Longest anchor-radius episode with low cluster speed, in seconds.",
    "stop_ratio": (
        "Accepted low-movement episode seconds divided by window span, bounded to [0, 1]."
    ),
    "large_turn_count": (
        "Wrapped heading changes >=100 degrees on segments >=max(8 m, 1.25x median accuracy)."
    ),
    "mean_accuracy": "Arithmetic mean of available reported horizontal accuracy, in meters.",
}

# Engineering thresholds for this first synthetic version; not physiological limits.
FEATURE_CONFIG = {
    "tortuosity_direct_floor_m": 10.0,
    "tortuosity_cap": 10.0,
    "stop_radius_accuracy_factor": 3.0,
    "stop_radius_min_m": 8.0,
    "stop_radius_max_m": 30.0,
    "stop_episode_min_seconds": 15.0,
    "stop_max_cluster_speed_mps": 0.4,
    "turn_min_segment_m": 8.0,
    "large_turn_degrees": 100.0,
}


@dataclass(frozen=True)
class GpsPoint:
    timestamp: datetime
    latitude: float
    longitude: float
    accuracy_meters: float | None


class FeatureExtractionError(ValueError):
    """Raised when raw GPS cannot be converted to finite trajectory features."""


def haversine_meters(a: GpsPoint, b: GpsPoint) -> float:
    """Great-circle distance; sufficiently accurate for this local-scale project."""
    lat_a, lat_b = radians(a.latitude), radians(b.latitude)
    d_lat = lat_b - lat_a
    d_lon = radians(b.longitude - a.longitude)
    h = sin(d_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * atan2(sqrt(min(1.0, h)), sqrt(max(0.0, 1.0 - h)))


def _local_vector(a: GpsPoint, b: GpsPoint) -> tuple[float, float]:
    """Return east/north metres using a local equirectangular approximation."""
    mean_latitude = radians((a.latitude + b.latitude) / 2.0)
    east = radians(b.longitude - a.longitude) * EARTH_RADIUS_METERS * cos(mean_latitude)
    north = radians(b.latitude - a.latitude) * EARTH_RADIUS_METERS
    return east, north


def _seconds_between(a: datetime, b: datetime) -> float:
    try:
        return (b - a).total_seconds()
    except TypeError as exc:
        raise FeatureExtractionError("timestamps must use a consistent timezone") from exc


def _validate_point(point: GpsPoint) -> None:
    if not isinstance(point.timestamp, datetime):
        raise FeatureExtractionError("timestamp must be a datetime")
    if point.timestamp.tzinfo is None or point.timestamp.utcoffset() is None:
        raise FeatureExtractionError("timestamp must be timezone-aware")
    if not all(isfinite(value) for value in (point.latitude, point.longitude)):
        raise FeatureExtractionError("coordinates must be finite")
    if not -90 <= point.latitude <= 90 or not -180 <= point.longitude <= 180:
        raise FeatureExtractionError("coordinates are outside WGS84 bounds")


def _stop_features(
    points: Sequence[GpsPoint],
    median_accuracy: float,
) -> tuple[float, float]:
    span_seconds = _seconds_between(points[0].timestamp, points[-1].timestamp)
    radius = min(
        FEATURE_CONFIG["stop_radius_max_m"],
        max(
            FEATURE_CONFIG["stop_radius_min_m"],
            median_accuracy * FEATURE_CONFIG["stop_radius_accuracy_factor"],
        ),
    )
    minimum_episode = FEATURE_CONFIG["stop_episode_min_seconds"]
    stop_seconds = 0.0
    longest_stop = 0.0
    start_index = 0
    while start_index < len(points) - 1:
        end_index = start_index + 1
        while end_index < len(points):
            if haversine_meters(points[start_index], points[end_index]) > radius:
                break
            end_index += 1
        duration = _seconds_between(
            points[start_index].timestamp,
            points[end_index - 1].timestamp,
        )
        cluster_speed = (
            haversine_meters(points[start_index], points[end_index - 1]) / duration
            if duration > 0
            else float("inf")
        )
        if (
            duration >= minimum_episode
            and cluster_speed <= FEATURE_CONFIG["stop_max_cluster_speed_mps"]
        ):
            stop_seconds += duration
            longest_stop = max(longest_stop, duration)
        start_index = max(end_index, start_index + 1)
    return longest_stop, min(1.0, stop_seconds / span_seconds)


def extract_features(points: Sequence[GpsPoint]) -> dict[str, float]:
    """Extract the fixed feature vector. Input order is preserved and validated."""
    if len(points) < 2:
        raise FeatureExtractionError("at least two GPS points are required")
    for point in points:
        _validate_point(point)

    durations = [
        _seconds_between(points[index].timestamp, points[index + 1].timestamp)
        for index in range(len(points) - 1)
    ]
    if any(duration <= 0 for duration in durations):
        raise FeatureExtractionError("timestamps must be strictly increasing")

    distances = [haversine_meters(a, b) for a, b in pairwise(points)]
    speeds = [distance / duration for distance, duration in zip(distances, durations, strict=True)]
    if not all(isfinite(value) for value in distances + speeds):
        raise FeatureExtractionError("non-finite distance or speed")

    accuracy_values = [
        point.accuracy_meters
        for point in points
        if point.accuracy_meters is not None and isfinite(point.accuracy_meters)
    ]
    if not accuracy_values or any(value < 0 for value in accuracy_values):
        raise FeatureExtractionError("valid accuracy measurements are required")

    path_length = sum(distances)
    direct_distance = haversine_meters(points[0], points[-1])
    tortuosity = min(
        FEATURE_CONFIG["tortuosity_cap"],
        path_length / max(direct_distance, FEATURE_CONFIG["tortuosity_direct_floor_m"]),
    )
    longest_stop_seconds, stop_ratio = _stop_features(points, median(accuracy_values))

    headings: list[float] = []
    minimum_turn_segment = max(
        FEATURE_CONFIG["turn_min_segment_m"],
        median(accuracy_values) * 1.25,
    )
    for index, distance in enumerate(distances):
        if distance < minimum_turn_segment:
            headings.append(float("nan"))
            continue
        east, north = _local_vector(points[index], points[index + 1])
        headings.append(atan2(east, north))

    large_turn_count = 0
    for before, after in pairwise(headings):
        if not isfinite(before) or not isfinite(after):
            continue
        # atan2(sin(delta), cos(delta)) correctly wraps 359° -> 1° to about 2°.
        delta = atan2(sin(after - before), cos(after - before))
        if abs(degrees(delta)) >= FEATURE_CONFIG["large_turn_degrees"]:
            large_turn_count += 1

    feature_values = {
        "median_speed": median(speeds),
        "speed_std": pstdev(speeds),
        "max_speed": max(speeds),
        "path_length": path_length,
        "direct_distance": direct_distance,
        "tortuosity": tortuosity,
        "longest_stop_seconds": longest_stop_seconds,
        "stop_ratio": stop_ratio,
        "large_turn_count": float(large_turn_count),
        "mean_accuracy": mean(accuracy_values),
    }
    if tuple(feature_values) != FEATURE_NAMES:
        raise AssertionError("feature order changed without updating FEATURE_NAMES")
    if not all(isfinite(value) for value in feature_values.values()):
        raise FeatureExtractionError("feature vector contains non-finite values")
    return feature_values
