from datetime import UTC, datetime, timedelta

from experiments.trajectory_anomaly.simulate import generate_trip

from app.ml.trajectory_anomaly.features import GpsPoint
from app.ml.trajectory_anomaly.quality import assess_quality


def valid_points() -> list[GpsPoint]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        GpsPoint(
            timestamp=start + timedelta(seconds=index * 10),
            latitude=23.1189 + index * 0.00001,
            longitude=113.2351,
            accuracy_meters=8.0,
        )
        for index in range(40)
    ]


def test_reasonable_walk_passes_quality_gate() -> None:
    quality = assess_quality(valid_points())

    assert quality.valid
    assert quality.reason_codes == ()


def test_gps_dropout_is_unknown_at_quality_gate() -> None:
    trip = generate_trip("gps_dropout", seed=42, trajectory_id="dropout-test")

    quality = assess_quality(trip.points)

    assert not quality.valid
    assert "TIMESTAMP_GAP" in quality.reason_codes


def test_poor_accuracy_is_unknown_at_quality_gate() -> None:
    trip = generate_trip("poor_accuracy", seed=43, trajectory_id="accuracy-test")

    quality = assess_quality(trip.points)

    assert not quality.valid
    assert "POOR_MEDIAN_ACCURACY" in quality.reason_codes


def test_non_monotonic_timestamp_is_unknown_and_not_sorted() -> None:
    points = valid_points()
    points[12] = GpsPoint(
        timestamp=points[10].timestamp,
        latitude=points[12].latitude,
        longitude=points[12].longitude,
        accuracy_meters=points[12].accuracy_meters,
    )

    quality = assess_quality(points)

    assert not quality.valid
    assert "NON_MONOTONIC_TIMESTAMPS" in quality.reason_codes


def test_severe_timestamp_gap_is_unknown() -> None:
    trip = generate_trip("severe_timestamp_gap", seed=44, trajectory_id="gap-test")

    quality = assess_quality(trip.points)

    assert not quality.valid
    assert "TIMESTAMP_GAP" in quality.reason_codes


def test_too_few_points_and_short_span_are_unknown() -> None:
    points = valid_points()[:10]

    quality = assess_quality(points)

    assert not quality.valid
    assert "TOO_FEW_POINTS" in quality.reason_codes
    assert "SHORT_TIME_SPAN" in quality.reason_codes
