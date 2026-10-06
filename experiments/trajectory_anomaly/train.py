"""Fit the final production artifact after standalone evaluation is reviewed."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from statistics import median

import sklearn
from experiments.trajectory_anomaly.dataset import (
    RESULTS_DIR,
    DatasetRecord,
    feature_rows,
    generator_version,
    is_post_event_window,
    prepare_dataset,
    write_dataset_summary,
)
from experiments.trajectory_anomaly.simulate import ANOMALY_SCENARIOS

from app.ml.trajectory_anomaly.model import (
    ARTIFACT_DIR,
    TARGET_VALIDATION_FPR,
    ModelBundle,
    anomaly_scores,
    build_metadata,
    calibrate_threshold,
    fit_model,
    load_artifact,
    save_artifact,
)


def train_production_artifact(
    records: list[DatasetRecord],
    artifact_dir: Path | None = None,
) -> ModelBundle:
    train_normal = feature_rows(records, "train_normal")
    validation_normal = feature_rows(records, "validation_normal")
    if not train_normal or not validation_normal:
        raise RuntimeError("normal train and validation splits must both be non-empty")
    train_trajectory_count = len(
        {record.trip.trajectory_id for record in records if record.split == "train_normal"}
    )
    validation_trajectory_count = len(
        {
            record.trip.trajectory_id
            for record in records
            if record.split == "validation_normal"
        }
    )

    # Calibrate only on held-out validation trajectories, before they are added to final fit.
    calibration_model = fit_model(train_normal, random_state=42)
    threshold = calibrate_threshold(
        calibration_model,
        validation_normal,
        target_fpr=TARGET_VALIDATION_FPR,
    )
    final_rows = train_normal + validation_normal
    production_model = fit_model(final_rows, random_state=42)
    metadata = build_metadata(
        threshold=threshold,
        random_state=42,
        training_window_count=len(final_rows),
        training_trajectory_count=train_trajectory_count + validation_trajectory_count,
        calibration_training_window_count=len(train_normal),
        calibration_training_trajectory_count=train_trajectory_count,
        generator_version=generator_version(),
        sklearn_version=sklearn.__version__,
        target_fpr=TARGET_VALIDATION_FPR,
    )
    bundle = ModelBundle(model=production_model, metadata=metadata)
    output_dir = artifact_dir or ARTIFACT_DIR
    save_artifact(bundle, output_dir)
    loaded_bundle = load_artifact(output_dir)
    if loaded_bundle.metadata != metadata:
        raise RuntimeError("saved artifact metadata does not match the trained model metadata")
    return loaded_bundle


def evaluate_production_artifact(
    bundle: ModelBundle,
    records: list[DatasetRecord],
) -> dict[str, object]:
    threshold = float(bundle.metadata["threshold"])
    test_normal = [
        record for record in records if record.split == "test_normal" and record.features
    ]
    normal_scores = anomaly_scores(bundle.model, [record.features for record in test_normal])
    scenario_metrics: dict[str, dict[str, object]] = {}
    test_trip_predictions: dict[str, bool] = {}
    for record, score in zip(test_normal, normal_scores, strict=True):
        test_trip_predictions[record.trip.trajectory_id] = (
            test_trip_predictions.get(record.trip.trajectory_id, False)
            or score > threshold
        )
    for scenario in ANOMALY_SCENARIOS:
        stress_records = [
            record
            for record in records
            if record.split == "stress_test" and record.trip.scenario == scenario
        ]
        valid_records = [record for record in stress_records if record.features]
        scores = (
            anomaly_scores(bundle.model, [record.features for record in valid_records])
            if valid_records
            else []
        )
        trip_predictions: dict[str, bool] = {}
        for record, score in zip(valid_records, scores, strict=True):
            trip_predictions[record.trip.trajectory_id] = (
                trip_predictions.get(record.trip.trajectory_id, False)
                or score > threshold
            )
        eligible_pairs = [
            (record, score)
            for record, score in zip(valid_records, scores, strict=True)
            if is_post_event_window(record)
        ]
        eligible_trip_predictions: dict[str, bool] = {}
        detection_latencies: dict[str, float] = {}
        for record, score in eligible_pairs:
            trajectory_id = record.trip.trajectory_id
            eligible_trip_predictions[trajectory_id] = (
                eligible_trip_predictions.get(trajectory_id, False)
                or score > threshold
            )
            if score > threshold and trajectory_id not in detection_latencies:
                onset = record.trip.behavior_start_seconds
                if onset is not None:
                    event_start = record.trip.points[0].timestamp + timedelta(seconds=onset)
                    detection_latencies[trajectory_id] = (
                        record.window_end - event_start
                    ).total_seconds()
        event_aware_rate = (
            sum(eligible_trip_predictions.values()) / len(eligible_trip_predictions)
            if eligible_trip_predictions
            and any(record.trip.behavior_start_seconds is not None for record in stress_records)
            else None
        )
        scenario_metrics[scenario] = {
            "trajectory_count": len(
                {record.trip.trajectory_id for record in stress_records}
            ),
            "window_count": len(stress_records),
            "quality_valid_count": len(valid_records),
            "quality_unknown_rate": (
                (len(stress_records) - len(valid_records)) / len(stress_records)
                if stress_records
                else None
            ),
            "attention_rate_when_valid": (
                sum(score > threshold for score in scores) / len(scores) if scores else None
            ),
            "event_eligible_window_count": len(eligible_pairs),
            "attention_rate_after_event_evidence": (
                sum(score > threshold for _, score in eligible_pairs) / len(eligible_pairs)
                if eligible_pairs
                else None
            ),
            "trajectory_detection_rate_any_window": (
                sum(trip_predictions.values()) / len(trip_predictions)
                if trip_predictions
                else None
            ),
            "trajectory_detection_rate_after_event_evidence": event_aware_rate,
            "minimum_detected_event_latency_seconds": (
                min(detection_latencies.values()) if detection_latencies else None
            ),
            "median_detected_event_latency_seconds": (
                median(detection_latencies.values())
                if detection_latencies
                else None
            ),
        }
    return {
        "model_version": bundle.metadata["model_version"],
        "window_seconds": bundle.metadata["window_seconds"],
        "test_normal_window_count": len(test_normal),
        "test_normal_trajectory_count": len(
            {record.trip.trajectory_id for record in test_normal}
        ),
        "test_normal_fpr": sum(score > threshold for score in normal_scores) / len(normal_scores),
        "test_normal_any_window_trip_fpr": (
            sum(test_trip_predictions.values()) / len(test_trip_predictions)
            if test_trip_predictions
            else None
        ),
        "synthetic_stress_scenarios": scenario_metrics,
    }


def main() -> None:
    records = prepare_dataset()
    write_dataset_summary(records)
    bundle = train_production_artifact(records)
    production_metrics = evaluate_production_artifact(bundle, records)
    summary_path = RESULTS_DIR / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["final_production_artifact_test"] = production_metrics
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "train_normal": len(feature_rows(records, "train_normal")),
                "validation_normal": len(feature_rows(records, "validation_normal")),
                "final_training_window_count": bundle.metadata["training_window_count"],
                "final_training_trajectory_count": bundle.metadata[
                    "training_trajectory_count"
                ],
                "threshold": bundle.metadata["threshold"],
                "artifact_dir": str(ARTIFACT_DIR),
                "dataset_summary": str(RESULTS_DIR / "dataset_summary.csv"),
                "final_production_artifact_test": production_metrics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
