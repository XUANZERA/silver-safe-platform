from datetime import UTC, datetime, timedelta

import pytest

from app.ml.trajectory_anomaly.features import (
    FEATURE_NAMES,
    FeatureExtractionError,
    GpsPoint,
    extract_features,
)
from app.ml.trajectory_anomaly.model import ordered_feature_values

REFERENCE_LAT = 23.1189
REFERENCE_LON = 113.2351
EARTH_RADIUS = 6_371_000.0


def gps_point(timestamp: datetime, x: float, y: float, accuracy: float = 5.0) -> GpsPoint:
    import math

    latitude = REFERENCE_LAT + math.degrees(y / EARTH_RADIUS)
    longitude = REFERENCE_LON + math.degrees(
        x / (EARTH_RADIUS * math.cos(math.radians(REFERENCE_LAT)))
    )
    return GpsPoint(timestamp, latitude, longitude, accuracy)


def points_from_xy(positions: list[tuple[float, float]]) -> list[GpsPoint]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        gps_point(start + timedelta(seconds=10 * index), *xy) for index, xy in enumerate(positions)
    ]


def test_straight_walk_has_finite_feature_vector_in_fixed_order() -> None:
    points = points_from_xy([(index * 10.0, 0.0) for index in range(31)])

    features = extract_features(points)

    assert tuple(features) == FEATURE_NAMES
    assert features["median_speed"] == pytest.approx(1.0, abs=0.01)
    assert features["path_length"] == pytest.approx(300.0, abs=0.01)
    assert features["tortuosity"] == pytest.approx(1.0, abs=0.01)
    assert features["large_turn_count"] == 0


def test_long_stationary_episode_increases_stop_feature() -> None:
    positions = [(index * 10.0, 0.0) for index in range(10)]
    positions.extend([(90.0, 0.0)] * 13)
    positions.extend([(90.0 + 10.0 * index, 0.0) for index in range(1, 11)])

    features = extract_features(points_from_xy(positions))

    assert features["longest_stop_seconds"] >= 100
    assert features["stop_ratio"] > 0.3


def test_repeated_backtracking_increases_large_turn_count() -> None:
    straight = points_from_xy([(index * 100.0, 0.0) for index in range(20)])
    backtracking = points_from_xy([(0.0 if index % 2 == 0 else 100.0, 0.0) for index in range(20)])

    assert extract_features(backtracking)["large_turn_count"] >= 3
    assert extract_features(straight)["large_turn_count"] == 0


def test_turn_angle_wraparound_does_not_count_359_to_1_as_large_turn() -> None:
    import math

    start = datetime(2025, 1, 1, tzinfo=UTC)
    positions = []
    for angle_degrees in (-1.0, 1.0):
        angle = math.radians(angle_degrees)
        positions.append((100.0 * math.sin(angle), 100.0 * math.cos(angle)))
    points = [
        gps_point(start + timedelta(seconds=10 * index), *xy) for index, xy in enumerate(positions)
    ]

    assert extract_features(points)["large_turn_count"] == 0


def test_duplicate_timestamp_is_not_silently_repaired() -> None:
    points = points_from_xy([(index * 10.0, 0.0) for index in range(4)])
    points[2] = GpsPoint(points[1].timestamp, points[2].latitude, points[2].longitude, 5.0)

    with pytest.raises(FeatureExtractionError, match="strictly increasing"):
        extract_features(points)


def test_reordered_feature_columns_are_rejected() -> None:
    features = extract_features(points_from_xy([(index * 10.0, 0.0) for index in range(4)]))
    reversed_features = dict(reversed(tuple(features.items())))

    with pytest.raises(ValueError, match="feature order mismatch"):
        ordered_feature_values(reversed_features)
