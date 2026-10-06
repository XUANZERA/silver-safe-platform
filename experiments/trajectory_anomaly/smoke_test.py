"""Artifact load and deterministic raw-GPS smoke scenarios."""

from __future__ import annotations

import json
from datetime import timedelta

from experiments.trajectory_anomaly.simulate import (
    SIMULATION_START,
    generate_trip,
    local_xy_to_wgs84,
)

from app.ml.trajectory_anomaly.features import FEATURE_NAMES, GpsPoint
from app.ml.trajectory_anomaly.inference import infer_trajectory
from app.ml.trajectory_anomaly.model import ARTIFACT_DIR, load_artifact
from app.ml.trajectory_anomaly.quality import assess_quality


def repeated_ab_trajectory() -> tuple[GpsPoint, ...]:
    start = SIMULATION_START
    a = local_xy_to_wgs84(0.0, 0.0)
    b = local_xy_to_wgs84(0.0, 100.0)
    return tuple(
        GpsPoint(
            timestamp=start + timedelta(seconds=15 * index),
            latitude=(a if index % 2 == 0 else b)[0],
            longitude=(a if index % 2 == 0 else b)[1],
            accuracy_meters=8.0,
        )
        for index in range(41)
    )


def in_window_timestamp_gap_trajectory() -> tuple[GpsPoint, ...]:
    start = SIMULATION_START
    coordinates = local_xy_to_wgs84(0.0, 0.0)
    points: list[GpsPoint] = []
    for index in range(41):
        elapsed = index * 15 + (180 if index >= 20 else 0)
        points.append(
            GpsPoint(
                timestamp=start + timedelta(seconds=elapsed),
                latitude=coordinates[0] + index * 0.00001,
                longitude=coordinates[1],
                accuracy_meters=8.0,
            )
        )
    return tuple(points)


def main() -> None:
    model_path = ARTIFACT_DIR / "isolation_forest.joblib"
    metadata_path = ARTIFACT_DIR / "metadata.json"
    assert model_path.is_file(), f"missing artifact: {model_path}"
    assert metadata_path.is_file(), f"missing metadata: {metadata_path}"
    bundle = load_artifact()
    assert tuple(bundle.metadata["feature_names"]) == FEATURE_NAMES
    assert int(bundle.model.n_features_in_) == len(FEATURE_NAMES)

    normal = generate_trip("normal_walk", seed=1000, trajectory_id="smoke-new-normal")
    normal_result = infer_trajectory(normal.points, bundle)
    assert assess_quality(normal.points).valid
    assert normal_result.status.value == "NORMAL", normal_result

    backtracking = repeated_ab_trajectory()
    backtracking_quality = assess_quality(backtracking)
    assert backtracking_quality.valid
    backtracking_result = infer_trajectory(backtracking, bundle)

    long_stop = generate_trip("long_stop", seed=42, trajectory_id="smoke-long-stop")
    long_stop_quality = assess_quality(long_stop.points)
    assert long_stop_quality.valid
    long_stop_result = infer_trajectory(long_stop.points, bundle)

    dropout = in_window_timestamp_gap_trajectory()
    dropout_result = infer_trajectory(dropout, bundle)
    assert dropout_result.status.value == "UNKNOWN"
    assert "TIMESTAMP_GAP" in dropout_result.reason_codes

    print(
        json.dumps(
            {
                "artifact_load": "PASS",
                "metadata_feature_names_match": True,
                "new_normal": {
                    "quality": "VALID",
                    "status": normal_result.status.value,
                    "score": normal_result.score,
                },
                "repeated_A_B_backtracking": {
                    "quality": "VALID",
                    "status": backtracking_result.status.value,
                    "score": backtracking_result.score,
                    "reason_codes": backtracking_result.reason_codes,
                },
                "long_stop": {
                    "quality": "VALID",
                    "status": long_stop_result.status.value,
                    "score": long_stop_result.score,
                    "reason_codes": long_stop_result.reason_codes,
                },
                "gps_dropout": {
                    "status": dropout_result.status.value,
                    "reason_codes": dropout_result.reason_codes,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
