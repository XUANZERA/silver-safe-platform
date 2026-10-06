"""Isolation Forest training, scoring, and artifact persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil, isfinite
from pathlib import Path

from app.ml.trajectory_anomaly.features import FEATURE_DEFINITIONS, FEATURE_NAMES
from app.ml.trajectory_anomaly.windows import (
    WINDOW_DEFINITION,
    WINDOW_MINIMUM_COVERAGE_RATIO,
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_FILENAME = "isolation_forest.joblib"
METADATA_FILENAME = "metadata.json"
TARGET_VALIDATION_FPR = 0.05
SCORE_DIRECTION = "higher_is_more_abnormal; anomaly_score=-decision_function"
ISOLATION_FOREST_CONFIG = {
    "n_estimators": 200,
    "max_samples": "auto",
    "max_features": 1.0,
    "contamination": "auto",
    "n_jobs": -1,
}


class TrajectoryModelError(RuntimeError):
    """Base error for trajectory model loading and scoring failures."""


class ArtifactValidationError(TrajectoryModelError):
    """The stored model artifact or its metadata is invalid for this runtime."""


@dataclass(frozen=True)
class ModelBundle:
    model: object
    metadata: dict[str, object]


def ordered_feature_values(features: Mapping[str, float]) -> list[float]:
    actual_order = tuple(features)
    if actual_order != FEATURE_NAMES:
        raise ValueError(f"feature order mismatch: expected {FEATURE_NAMES}, got {actual_order}")
    values = [float(features[name]) for name in FEATURE_NAMES]
    if any(not isfinite(value) for value in values):
        raise ValueError("feature values must all be finite")
    return values


def _feature_matrix(rows: Sequence[Mapping[str, float]]):
    import numpy as np

    if not rows:
        raise ValueError("at least one feature row is required")
    return np.asarray([ordered_feature_values(row) for row in rows], dtype=float)


def create_model(random_state: int = 42):
    from sklearn.ensemble import IsolationForest

    return IsolationForest(random_state=random_state, **ISOLATION_FOREST_CONFIG)


def fit_model(
    rows: Sequence[Mapping[str, float]],
    *,
    random_state: int = 42,
):
    model = create_model(random_state=random_state)
    model.fit(_feature_matrix(rows))
    return model


def anomaly_scores(model: object, rows: Sequence[Mapping[str, float]]) -> list[float]:
    """Return -decision_function; larger values mean more statistically unusual."""
    import numpy as np

    matrix = _feature_matrix(rows)
    try:
        raw_scores = model.decision_function(matrix)
        values = np.asarray(raw_scores, dtype=float).reshape(-1)
    except Exception as error:
        raise TrajectoryModelError("trajectory model scoring failed") from error
    if values.size != len(rows):
        raise TrajectoryModelError("trajectory model returned an unexpected score count")
    scores = [-float(value) for value in values]
    if any(not isfinite(score) for score in scores):
        raise TrajectoryModelError("trajectory model returned a non-finite score")
    return scores


def calibrate_threshold(
    model: object,
    validation_normal: Sequence[Mapping[str, float]],
    *,
    target_fpr: float = TARGET_VALIDATION_FPR,
) -> float:
    if not 0 < target_fpr < 1:
        raise ValueError("target_fpr must be strictly between zero and one")
    scores = sorted(anomaly_scores(model, validation_normal))
    if not scores:
        raise ValueError("validation_normal must not be empty")
    index = max(0, min(len(scores) - 1, ceil((1 - target_fpr) * len(scores)) - 1))
    return float(scores[index])


def build_metadata(
    *,
    threshold: float,
    random_state: int,
    training_window_count: int,
    training_trajectory_count: int,
    calibration_training_window_count: int,
    calibration_training_trajectory_count: int,
    generator_version: str,
    sklearn_version: str,
    window_seconds: int = WINDOW_SECONDS,
    target_fpr: float = TARGET_VALIDATION_FPR,
) -> dict[str, object]:
    if isinstance(threshold, bool) or not isfinite(float(threshold)):
        raise ArtifactValidationError("artifact threshold must be finite")
    if window_seconds <= 0:
        raise ArtifactValidationError("artifact window length must be positive")
    return {
        "model_name": "trajectory_isolation_forest",
        "model_version": "v2",
        "feature_names": list(FEATURE_NAMES),
        "feature_definitions": FEATURE_DEFINITIONS,
        "threshold": float(threshold),
        "window_seconds": int(window_seconds),
        "window_definition": WINDOW_DEFINITION,
        "window_step_seconds": WINDOW_STEP_SECONDS,
        "window_minimum_coverage_ratio": WINDOW_MINIMUM_COVERAGE_RATIO,
        "score_direction": SCORE_DIRECTION,
        "training_data": "synthetic_normal_only",
        "training_window_count": int(training_window_count),
        "training_trajectory_count": int(training_trajectory_count),
        "threshold_calibration_training_window_count": int(
            calibration_training_window_count
        ),
        "threshold_calibration_training_trajectory_count": int(
            calibration_training_trajectory_count
        ),
        "synthetic_generator_version": generator_version,
        "random_state": int(random_state),
        "model_parameters": {**ISOLATION_FOREST_CONFIG, "random_state": int(random_state)},
        "sklearn_version": sklearn_version,
        "target_validation_fpr": float(target_fpr),
        "preprocessing": "none; Isolation Forest uses random feature splits",
        "threshold_calibration": "held_out_validation_normal_only",
    }


def save_artifact(
    bundle: ModelBundle,
    artifact_dir: Path = ARTIFACT_DIR,
) -> tuple[Path, Path]:
    import joblib

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / MODEL_FILENAME
    metadata_path = artifact_dir / METADATA_FILENAME
    joblib.dump(bundle.model, model_path)
    metadata_path.write_text(
        json.dumps(bundle.metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return model_path, metadata_path


def load_artifact(artifact_dir: Path = ARTIFACT_DIR) -> ModelBundle:
    try:
        import joblib
        import sklearn

        model_path = artifact_dir / MODEL_FILENAME
        metadata_path = artifact_dir / METADATA_FILENAME
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ArtifactValidationError("artifact metadata must be an object")
        if metadata.get("sklearn_version") != sklearn.__version__:
            raise ArtifactValidationError(
                "artifact scikit-learn version does not match the installed version"
            )
        if tuple(metadata.get("feature_names", ())) != FEATURE_NAMES:
            raise ArtifactValidationError(
                "artifact feature names do not match the active extractor"
            )
        threshold = metadata.get("threshold")
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not isfinite(float(threshold))
        ):
            raise ArtifactValidationError("artifact calibration threshold must be finite")
        if metadata.get("score_direction") != SCORE_DIRECTION:
            raise ArtifactValidationError("artifact score direction is missing or unsupported")
        if metadata.get("window_seconds") != WINDOW_SECONDS:
            raise ArtifactValidationError("artifact window length does not match inference")
        if metadata.get("window_definition") != WINDOW_DEFINITION:
            raise ArtifactValidationError("artifact window definition does not match inference")
        if metadata.get("window_step_seconds") != WINDOW_STEP_SECONDS:
            raise ArtifactValidationError("artifact window step does not match evaluation")
        if metadata.get("window_minimum_coverage_ratio") != WINDOW_MINIMUM_COVERAGE_RATIO:
            raise ArtifactValidationError("artifact window coverage rule does not match inference")
        model = joblib.load(model_path)
        if int(model.n_features_in_) != len(FEATURE_NAMES):
            raise ArtifactValidationError(
                "artifact feature count does not match the active extractor"
            )
        return ModelBundle(model=model, metadata=metadata)
    except ArtifactValidationError:
        raise
    except Exception as error:
        raise ArtifactValidationError("trajectory model artifact could not be loaded") from error
