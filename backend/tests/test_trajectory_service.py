from datetime import timedelta
from types import SimpleNamespace

import pytest
from experiments.trajectory_anomaly.simulate import generate_trip

from app.ml.trajectory_anomaly.inference import inspect_reason_codes
from app.ml.trajectory_anomaly.model import (
    ArtifactValidationError,
    ModelBundle,
)
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS
from app.schemas.trajectory import TrajectoryAttentionStatus
from app.services import trajectory_anomaly as service


class StubModel:
    def decision_function(self, matrix):
        return [-0.5] * len(matrix)


class SequenceModel:
    def __init__(self, decisions):
        self.decisions = iter(decisions)

    def decision_function(self, matrix):
        decision = next(self.decisions)
        return [decision] * len(matrix)


def location_objects(points):
    return [
        SimpleNamespace(
            recorded_at=point.timestamp,
            latitude=point.latitude,
            longitude=point.longitude,
            accuracy_meters=point.accuracy_meters,
        )
        for point in points
    ]


def test_valid_input_gets_scored_and_model_is_loaded_once(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261006, trajectory_id="service-normal")
    calls = 0

    def load_bundle():
        nonlocal calls
        calls += 1
        return ModelBundle(
            model=StubModel(),
            metadata={
                "threshold": 0.1,
                "model_version": "test-v2",
                "window_seconds": WINDOW_SECONDS,
            },
        )

    monkeypatch.setattr(service, "load_artifact", load_bundle)
    service.clear_cached_model_for_tests()
    try:
        first = service.evaluate_locations(location_objects(trip.points))
        second = service.evaluate_locations(location_objects(trip.points))
    finally:
        service.clear_cached_model_for_tests()

    assert first.status == TrajectoryAttentionStatus.ATTENTION
    assert first.score == 0.5
    assert first.model_version == "test-v2"
    assert second.status == first.status
    assert calls == 1


def test_product_attention_requires_temporal_history(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261011, trajectory_id="service-warmup")
    history_end = trip.points[0].timestamp + timedelta(seconds=WINDOW_SECONDS + 60)
    short_history = [point for point in trip.points if point.timestamp <= history_end]
    monkeypatch.setattr(
        service,
        "load_artifact",
        lambda: ModelBundle(
            model=StubModel(),
            metadata={
                "threshold": 0.1,
                "model_version": "test-v2",
                "window_seconds": WINDOW_SECONDS,
            },
        ),
    )
    service.clear_cached_model_for_tests()
    try:
        result = service.evaluate_locations(location_objects(short_history))
    finally:
        service.clear_cached_model_for_tests()

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert result.score is None
    assert result.reason_codes == ["TEMPORAL_HISTORY_INSUFFICIENT"]


def test_temporal_attention_aggregates_scores_after_if_inference(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261012, trajectory_id="service-two-of-three")
    monkeypatch.setattr(
        service,
        "load_artifact",
        lambda: ModelBundle(
            model=SequenceModel([-0.5, 0.0, -0.5]),
            metadata={
                "threshold": 0.1,
                "model_version": "test-v2",
                "window_seconds": WINDOW_SECONDS,
            },
        ),
    )
    service.clear_cached_model_for_tests()
    try:
        result = service.evaluate_locations(location_objects(trip.points))
    finally:
        service.clear_cached_model_for_tests()

    assert result.status == TrajectoryAttentionStatus.ATTENTION
    assert result.score == 0.5


def test_missing_artifact_returns_unknown_without_breaking_service(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261007, trajectory_id="service-unavailable")

    def fail_to_load():
        raise ArtifactValidationError("artifact missing")

    monkeypatch.setattr(service, "load_artifact", fail_to_load)
    service.clear_cached_model_for_tests()
    try:
        result = service.evaluate_locations(location_objects(trip.points))
    finally:
        service.clear_cached_model_for_tests()

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert result.score is None
    assert result.reason_codes == ["MODEL_UNAVAILABLE"]


def test_model_runtime_error_returns_unknown(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261008, trajectory_id="service-runtime-error")

    class BrokenModel:
        def decision_function(self, matrix):
            raise RuntimeError("model runtime failure")

    monkeypatch.setattr(
        service,
        "load_artifact",
        lambda: ModelBundle(
            model=BrokenModel(),
            metadata={
                "threshold": 0.1,
                "model_version": "test-v2",
                "window_seconds": WINDOW_SECONDS,
            },
        ),
    )
    service.clear_cached_model_for_tests()
    try:
        result = service.evaluate_locations(location_objects(trip.points))
    finally:
        service.clear_cached_model_for_tests()

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert result.score is None
    assert result.reason_codes == ["MODEL_UNAVAILABLE"]


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_model_score_returns_unknown(monkeypatch, bad_score: float) -> None:
    trip = generate_trip("normal_walk", seed=20261010, trajectory_id="service-nonfinite-score")

    class NonFiniteModel:
        def decision_function(self, matrix):
            return [bad_score] * len(matrix)

    monkeypatch.setattr(
        service,
        "load_artifact",
        lambda: ModelBundle(
            model=NonFiniteModel(),
            metadata={
                "threshold": 0.1,
                "model_version": "test-v2",
                "window_seconds": WINDOW_SECONDS,
            },
        ),
    )
    service.clear_cached_model_for_tests()
    try:
        result = service.evaluate_locations(location_objects(trip.points))
    finally:
        service.clear_cached_model_for_tests()

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert result.score is None
    assert result.reason_codes == ["MODEL_UNAVAILABLE"]


def test_untyped_runtime_errors_are_not_hidden_as_model_errors(monkeypatch) -> None:
    trip = generate_trip("normal_walk", seed=20261009, trajectory_id="service-untyped-error")

    def fail_outside_model_boundary():
        raise ValueError("unexpected service error")

    monkeypatch.setattr(service, "_cached_model_bundle", fail_outside_model_boundary)
    try:
        service.evaluate_locations(location_objects(trip.points))
    except ValueError as error:
        assert str(error) == "unexpected service error"
    else:
        raise AssertionError("unexpected non-model exception was swallowed")


def test_quality_gate_runs_before_model_loading(monkeypatch) -> None:
    def fail_to_load():
        raise AssertionError("quality-invalid points must not trigger model loading")

    monkeypatch.setattr(service, "load_artifact", fail_to_load)
    service.clear_cached_model_for_tests()
    result = service.evaluate_locations([])

    assert result.status == TrajectoryAttentionStatus.UNKNOWN
    assert "TOO_FEW_POINTS" in result.reason_codes


def test_reason_rules_are_plain_feature_inspection() -> None:
    features = {
        "median_speed": 1.0,
        "speed_std": 0.0,
        "max_speed": 1.0,
        "path_length": 500.0,
        "direct_distance": 50.0,
        "tortuosity": 10.0,
        "longest_stop_seconds": 600.0,
        "stop_ratio": 0.5,
        "large_turn_count": 6.0,
        "mean_accuracy": 8.0,
    }

    assert inspect_reason_codes(features) == (
        "LONG_STOP",
        "HIGH_TORTUOSITY",
        "REPEATED_TURNS",
    )
