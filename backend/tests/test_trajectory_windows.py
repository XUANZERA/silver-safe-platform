from datetime import UTC, datetime, timedelta

from app.ml.trajectory_anomaly.features import FEATURE_NAMES, GpsPoint
from app.ml.trajectory_anomaly.inference import (
    TrajectoryAttentionStatus,
    infer_trajectory,
)
from app.ml.trajectory_anomaly.model import ModelBundle
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS, latest_window


class PathLengthThresholdModel:
    """A deterministic probe that would flip on cumulative, unwindowed distance."""

    def decision_function(self, matrix):
        path_length_index = FEATURE_NAMES.index("path_length")
        return [500.0 - row[path_length_index] for row in matrix]


def straight_line_points() -> list[GpsPoint]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        GpsPoint(
            timestamp=start + timedelta(seconds=index * 10),
            latitude=23.1189 + (0.8 * index * 10) / 111_195,
            longitude=113.2351,
            accuracy_meters=8.0,
        )
        for index in range(181)
    ]


def test_constant_speed_sliding_windows_do_not_change_with_trip_age() -> None:
    points = straight_line_points()
    bundle = ModelBundle(
        model=PathLengthThresholdModel(),
        metadata={"threshold": 0.0, "window_seconds": WINDOW_SECONDS},
    )
    results = []

    for end_index in (60, 90, 120, 150, 180):
        result = infer_trajectory(points[: end_index + 1], bundle)
        results.append(result)

    assert all(result.status == TrajectoryAttentionStatus.NORMAL for result in results)
    assert max(result.score for result in results) - min(
        result.score for result in results
    ) < 1e-6


def test_production_window_is_exactly_the_frozen_elapsed_time_length() -> None:
    points = straight_line_points()
    window = latest_window(points)

    assert window.complete
    assert window.end_at - window.start_at == timedelta(seconds=WINDOW_SECONDS)
    assert window.observed_span_seconds == WINDOW_SECONDS


def test_partial_window_is_unknown_instead_of_being_scored() -> None:
    points = straight_line_points()[:54]
    bundle = ModelBundle(
        model=PathLengthThresholdModel(),
        metadata={"threshold": 0.0, "window_seconds": WINDOW_SECONDS},
    )

    result = infer_trajectory(points, bundle)

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert result.score is None
    assert "INCOMPLETE_WINDOW" in result.reason_codes
