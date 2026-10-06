"""Trajectory-level splits and shared simulator -> quality -> feature pipeline."""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from experiments.trajectory_anomaly.simulate import (
    ANOMALY_SCENARIOS,
    DEFAULT_DATASET_SEED,
    DEFAULT_NORMAL_TRIPS_PER_SCENARIO,
    DEFAULT_STRESS_TRIPS_PER_SCENARIO,
    GENERATOR_VERSION,
    NORMAL_SCENARIOS,
    SimulatedTrip,
    generate_dataset,
)

from app.ml.trajectory_anomaly.features import FEATURE_NAMES, GpsPoint, extract_features
from app.ml.trajectory_anomaly.quality import QualityResult, assess_quality
from app.ml.trajectory_anomaly.windows import (
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
    sliding_windows,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
SPLIT_SEED = 42
MIN_EVENT_EVIDENCE_SECONDS = {"long_stop": 300.0}
BEHAVIORAL_SCENARIOS = (
    "long_stop",
    "repeated_backtracking",
    "circular_wandering",
    "abnormal_speed_pattern",
)


@dataclass(frozen=True)
class DatasetRecord:
    trip: SimulatedTrip
    split: str
    window_start: datetime
    window_end: datetime
    points: tuple[GpsPoint, ...]
    quality: QualityResult
    features: dict[str, float] | None


def is_post_event_window(record: DatasetRecord) -> bool:
    """Whether the model window contains the predeclared minimum event evidence."""
    onset_seconds = record.trip.behavior_start_seconds
    if onset_seconds is None:
        return True
    event_start = record.trip.points[0].timestamp + timedelta(seconds=onset_seconds)
    minimum_evidence = MIN_EVENT_EVIDENCE_SECONDS.get(record.trip.scenario, 0.0)
    return record.window_end >= event_start + timedelta(seconds=minimum_evidence)


def prepare_dataset(
    *,
    normal_trips_per_scenario: int = DEFAULT_NORMAL_TRIPS_PER_SCENARIO,
    stress_trips_per_scenario: int = DEFAULT_STRESS_TRIPS_PER_SCENARIO,
    seed: int = DEFAULT_DATASET_SEED,
    window_seconds: int = WINDOW_SECONDS,
    step_seconds: int = WINDOW_STEP_SECONDS,
    selection_only: bool = False,
) -> list[DatasetRecord]:
    trips = generate_dataset(
        normal_trips_per_scenario=normal_trips_per_scenario,
        stress_trips_per_scenario=stress_trips_per_scenario,
        seed=seed,
    )
    splits: dict[str, str] = {}
    for scenario in NORMAL_SCENARIOS:
        ids = [trip.trajectory_id for trip in trips if trip.scenario == scenario]
        random.Random(SPLIT_SEED + NORMAL_SCENARIOS.index(scenario)).shuffle(ids)
        train_end = int(len(ids) * 0.6)
        validation_end = int(len(ids) * 0.8)
        for trip_id in ids[:train_end]:
            splits[trip_id] = "train_normal"
        for trip_id in ids[train_end:validation_end]:
            splits[trip_id] = "validation_normal"
        for trip_id in ids[validation_end:]:
            splits[trip_id] = "test_normal"
    for index, scenario in enumerate(ANOMALY_SCENARIOS):
        ids = [trip.trajectory_id for trip in trips if trip.scenario == scenario]
        random.Random(SPLIT_SEED + len(NORMAL_SCENARIOS) + index).shuffle(ids)
        development_end = max(1, int(len(ids) * 0.5))
        for trip_id in ids[:development_end]:
            splits[trip_id] = "development_anomaly"
        for trip_id in ids[development_end:]:
            splits[trip_id] = "stress_test"

    records: list[DatasetRecord] = []
    for trip in trips:
        split = splits[trip.trajectory_id]
        if selection_only and split not in (
            "train_normal",
            "validation_normal",
            "development_anomaly",
        ):
            continue
        if selection_only and trip.scenario not in (
            NORMAL_SCENARIOS + BEHAVIORAL_SCENARIOS
        ):
            continue
        windows = list(
            sliding_windows(
                trip.points,
                window_seconds=window_seconds,
                step_seconds=step_seconds,
            )
        )
        if trip.scenario in NORMAL_SCENARIOS and not windows:
            raise RuntimeError(
                "normal trajectory has no complete fixed windows: "
                f"{trip.trajectory_id}"
            )
        for window in windows:
            quality = assess_quality(window.points)
            if trip.scenario in NORMAL_SCENARIOS and not quality.valid:
                raise RuntimeError(
                    f"normal synthetic window failed quality gate: "
                    f"{trip.trajectory_id} {window.start_at.isoformat()} {quality.reason_codes}"
                )
            features = extract_features(window.points) if quality.valid else None
            records.append(
                DatasetRecord(
                    trip=trip,
                    split=split,
                    window_start=window.start_at,
                    window_end=window.end_at,
                    points=window.points,
                    quality=quality,
                    features=features,
                )
            )
    return records


def records_in(records: list[DatasetRecord], split: str) -> list[DatasetRecord]:
    return [record for record in records if record.split == split]


def feature_rows(records: list[DatasetRecord], split: str) -> list[dict[str, float]]:
    result = [
        record.features
        for record in records
        if record.split == split and record.features is not None
    ]
    return list(result)


def write_dataset_summary(records: list[DatasetRecord], path: Path = RESULTS_DIR) -> None:
    path.mkdir(parents=True, exist_ok=True)
    scenario_splits = {
        scenario: ("train_normal", "validation_normal", "test_normal")
        for scenario in NORMAL_SCENARIOS
    }
    scenario_splits.update(
        {
            scenario: ("development_anomaly", "stress_test")
            for scenario in ANOMALY_SCENARIOS
        }
    )
    with (path / "dataset_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "scenario",
                "split",
                "trajectory_count",
                "window_count",
                "quality_valid_count",
                "quality_unknown_count",
                "mean_points_per_window",
            ),
        )
        writer.writeheader()
        for scenario, allowed_splits in scenario_splits.items():
            for split in allowed_splits:
                selected = [
                    record
                    for record in records
                    if record.trip.scenario == scenario and record.split == split
                ]
                writer.writerow(
                    {
                        "scenario": scenario,
                        "split": split,
                        "trajectory_count": len(
                            {record.trip.trajectory_id for record in selected}
                        ),
                        "window_count": len(selected),
                        "quality_valid_count": sum(
                            record.quality.valid for record in selected
                        ),
                        "quality_unknown_count": sum(
                            not record.quality.valid for record in selected
                        ),
                        "mean_points_per_window": round(
                            sum(len(record.points) for record in selected) / len(selected), 2
                        )
                        if selected
                        else 0,
                    }
                )

    by_scenario: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        if record.features is not None:
            by_scenario[record.trip.scenario].append(record)
    with (path / "feature_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("scenario", "feature", "n", "mean", "std", "median", "p10", "p90"),
        )
        writer.writeheader()
        for scenario, samples in by_scenario.items():
            for feature_name in FEATURE_NAMES:
                values = sorted(
                    sample.features[feature_name] for sample in samples if sample.features
                )
                if not values:
                    continue
                mean_value = sum(values) / len(values)
                variance = sum((value - mean_value) ** 2 for value in values) / len(values)
                writer.writerow(
                    {
                        "scenario": scenario,
                        "feature": feature_name,
                        "n": len(values),
                        "mean": round(mean_value, 6),
                        "std": round(variance**0.5, 6),
                        "median": round(values[len(values) // 2], 6),
                        "p10": round(values[max(0, int(0.1 * (len(values) - 1)))], 6),
                        "p90": round(values[int(0.9 * (len(values) - 1))], 6),
                    }
                )


def scenario_counts(records: list[DatasetRecord]) -> dict[str, dict[str, int]]:
    trajectory_ids: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for record in records:
        trajectory_ids[record.trip.scenario][record.split].add(record.trip.trajectory_id)
    return {
        scenario: {split: len(ids) for split, ids in splits.items()}
        for scenario, splits in trajectory_ids.items()
    }


def generator_version() -> str:
    return GENERATOR_VERSION
