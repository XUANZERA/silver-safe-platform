import json

import pytest
import sklearn

from app.ml.trajectory_anomaly.features import FEATURE_NAMES
from app.ml.trajectory_anomaly.model import (
    SCORE_DIRECTION,
    ArtifactValidationError,
    TrajectoryModelError,
    anomaly_scores,
    load_artifact,
)
from app.ml.trajectory_anomaly.windows import (
    WINDOW_DEFINITION,
    WINDOW_MINIMUM_COVERAGE_RATIO,
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
)


class OutputModel:
    def __init__(self, output):
        self.output = output

    def decision_function(self, matrix):
        return [self.output] * len(matrix)


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_model_scores_are_rejected(bad_score: float) -> None:
    feature_row = dict.fromkeys(FEATURE_NAMES, 1.0)

    with pytest.raises(TrajectoryModelError, match="non-finite"):
        anomaly_scores(OutputModel(bad_score), [feature_row])


def test_model_runtime_error_is_wrapped_as_trajectory_model_error() -> None:
    class BrokenModel:
        def decision_function(self, matrix):
            raise RuntimeError("sklearn inference failed")

    with pytest.raises(TrajectoryModelError, match="scoring failed"):
        anomaly_scores(BrokenModel(), [dict.fromkeys(FEATURE_NAMES, 1.0)])


@pytest.mark.parametrize("bad_threshold", [float("nan"), float("inf"), float("-inf")])
def test_artifact_rejects_non_finite_threshold(tmp_path, bad_threshold: float) -> None:
    metadata = {
        "sklearn_version": sklearn.__version__,
        "feature_names": list(FEATURE_NAMES),
        "score_direction": SCORE_DIRECTION,
        "window_seconds": WINDOW_SECONDS,
        "window_definition": WINDOW_DEFINITION,
        "window_step_seconds": WINDOW_STEP_SECONDS,
        "window_minimum_coverage_ratio": WINDOW_MINIMUM_COVERAGE_RATIO,
        "threshold": bad_threshold,
    }
    (tmp_path / "metadata.json").write_text(
        json.dumps(metadata, allow_nan=True),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="threshold must be finite"):
        load_artifact(tmp_path)


@pytest.mark.parametrize("bad_threshold", [float("nan"), float("inf"), float("-inf")])
def test_calibration_bundle_cannot_use_non_finite_threshold(bad_threshold: float) -> None:
    from datetime import UTC, datetime, timedelta

    from app.ml.trajectory_anomaly.features import GpsPoint
    from app.ml.trajectory_anomaly.inference import infer_trajectory
    from app.ml.trajectory_anomaly.model import ModelBundle

    start = datetime(2025, 1, 1, tzinfo=UTC)
    points = [
        GpsPoint(
            timestamp=start + timedelta(seconds=index * 10),
            latitude=23.1189 + (0.8 * index * 10) / 111_195,
            longitude=113.2351,
            accuracy_meters=8.0,
        )
        for index in range(61)
    ]
    bundle = ModelBundle(
        model=OutputModel(0.0),
        metadata={"threshold": bad_threshold, "window_seconds": WINDOW_SECONDS},
    )

    with pytest.raises(ArtifactValidationError, match="threshold must be finite"):
        infer_trajectory(points, bundle)
