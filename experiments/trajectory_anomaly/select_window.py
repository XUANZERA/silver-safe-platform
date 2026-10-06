"""Choose a fixed production window using training and development splits only."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from statistics import median

from experiments.trajectory_anomaly.dataset import (
    MIN_EVENT_EVIDENCE_SECONDS,
    RESULTS_DIR,
    DatasetRecord,
    feature_rows,
    is_post_event_window,
    prepare_dataset,
)

from app.ml.trajectory_anomaly.model import (
    TARGET_VALIDATION_FPR,
    anomaly_scores,
    calibrate_threshold,
    fit_model,
)

CANDIDATE_WINDOWS_SECONDS = (10 * 60, 15 * 60)
DEVELOPMENT_SCENARIOS = ("long_stop", "repeated_backtracking")
VALIDATION_FPR_TOLERANCE = 0.01


def _trajectory_any_rate(records: list[DatasetRecord], predicted: list[bool]) -> float:
    per_trip: dict[str, bool] = defaultdict(bool)
    for record, is_attention in zip(records, predicted, strict=True):
        per_trip[record.trip.trajectory_id] |= is_attention
    return sum(per_trip.values()) / len(per_trip) if per_trip else 0.0


def _scenario_sensitivity(
    model: object,
    threshold: float,
    records: list[DatasetRecord],
    scenario: str,
) -> tuple[float, int]:
    selected = []
    for record in records:
        if record.trip.scenario != scenario or record.features is None:
            continue
        if is_post_event_window(record):
            selected.append(record)
    if not selected:
        return 0.0, 0
    scores = anomaly_scores(model, [record.features for record in selected])
    predictions = [score > threshold for score in scores]
    return _trajectory_any_rate(selected, predictions), len(
        {record.trip.trajectory_id for record in selected}
    )


def _observed_detection_latency(
    model: object,
    threshold: float,
    records: list[DatasetRecord],
) -> tuple[float | None, float | None, int]:
    selected = [
        record
        for record in records
        if record.trip.scenario in DEVELOPMENT_SCENARIOS
        and record.features is not None
        and record.trip.behavior_start_seconds is not None
    ]
    scores = anomaly_scores(model, [record.features for record in selected])
    latencies: dict[str, float] = {}
    for record, score in zip(selected, scores, strict=True):
        trajectory_id = record.trip.trajectory_id
        onset_at = record.trip.points[0].timestamp + timedelta(
            seconds=record.trip.behavior_start_seconds
        )
        if (
            score > threshold
            and is_post_event_window(record)
            and trajectory_id not in latencies
        ):
            latencies[trajectory_id] = (
                record.window_end - onset_at
            ).total_seconds()
    values = list(latencies.values())
    return (min(values), median(values), len(values)) if values else (None, None, 0)


def evaluate_candidate(records: list[DatasetRecord], window_seconds: int) -> dict[str, object]:
    train_rows = feature_rows(records, "train_normal")
    validation = [
        record
        for record in records
        if record.split == "validation_normal" and record.features is not None
    ]
    validation_rows = [record.features for record in validation]
    if not train_rows or not validation_rows:
        raise RuntimeError("window selection requires normal train and validation windows")

    model = fit_model(train_rows, random_state=42)
    threshold = calibrate_threshold(model, validation_rows)
    validation_scores = anomaly_scores(model, validation_rows)
    validation_predictions = [score > threshold for score in validation_scores]
    normal_fpr = sum(validation_predictions) / len(validation_predictions)
    normal_trip_fpr = _trajectory_any_rate(validation, validation_predictions)

    sensitivities: dict[str, float] = {}
    development_trip_counts: dict[str, int] = {}
    for scenario in DEVELOPMENT_SCENARIOS:
        sensitivity, count = _scenario_sensitivity(
            model,
            threshold,
            records,
            scenario,
        )
        sensitivities[scenario] = sensitivity
        development_trip_counts[scenario] = count
    minimum_observed_latency, median_observed_latency, detected_trip_count = (
        _observed_detection_latency(model, threshold, records)
    )

    return {
        "window_seconds": window_seconds,
        "window_minutes": window_seconds / 60,
        "train_normal_window_count": len(train_rows),
        "validation_normal_window_count": len(validation),
        "validation_normal_trajectory_count": len(
            {record.trip.trajectory_id for record in validation}
        ),
        "validation_normal_fpr": normal_fpr,
        "validation_normal_any_window_trip_fpr": normal_trip_fpr,
        "long_stop_development_sensitivity_per_trajectory": sensitivities["long_stop"],
        "backtracking_development_sensitivity_per_trajectory": sensitivities[
            "repeated_backtracking"
        ],
        "development_trajectory_counts": development_trip_counts,
        "minimum_decision_latency_seconds": window_seconds,
        "minimum_event_evidence_seconds": {
            scenario: MIN_EVENT_EVIDENCE_SECONDS.get(scenario, 0.0)
            for scenario in DEVELOPMENT_SCENARIOS
        },
        "minimum_observed_event_onset_to_attention_seconds": minimum_observed_latency,
        "median_observed_event_onset_to_attention_seconds": median_observed_latency,
        "development_trips_with_any_attention": detected_trip_count,
        "threshold": threshold,
    }


def choose_window(candidate_rows: list[dict[str, object]]) -> int:
    if not candidate_rows:
        raise ValueError("at least one candidate result is required")

    def rank(row: dict[str, object]) -> tuple[bool, float, float, int, float]:
        validation_gap = abs(float(row["validation_normal_fpr"]) - TARGET_VALIDATION_FPR)
        fpr_in_band = validation_gap <= VALIDATION_FPR_TOLERANCE
        worst_sensitivity = min(
            float(row["long_stop_development_sensitivity_per_trajectory"]),
            float(row["backtracking_development_sensitivity_per_trajectory"]),
        )
        mean_sensitivity = (
            float(row["long_stop_development_sensitivity_per_trajectory"])
            + float(row["backtracking_development_sensitivity_per_trajectory"])
        ) / 2
        # Require a validation FPR within one point of target, then prioritize
        # worst-case and mean sensitivity, followed by latency and FPR distance.
        return (
            fpr_in_band,
            worst_sensitivity,
            mean_sensitivity,
            -int(row["minimum_decision_latency_seconds"]),
            -validation_gap,
        )

    winner = max(candidate_rows, key=rank)
    return int(winner["window_seconds"])


def select_window() -> dict[str, object]:
    candidate_rows: list[dict[str, object]] = []
    for window_seconds in CANDIDATE_WINDOWS_SECONDS:
        development_records = prepare_dataset(
            window_seconds=window_seconds,
            selection_only=True,
        )
        candidate_rows.append(evaluate_candidate(development_records, window_seconds))

    selected_window = choose_window(candidate_rows)
    result: dict[str, object] = {
        "selected_window_seconds": selected_window,
        "selection_data": ["train_normal", "validation_normal", "development_anomaly"],
        "excluded_data": ["test_normal", "stress_test"],
        "development_scenarios": list(DEVELOPMENT_SCENARIOS),
        "latency_definition": (
            "first ATTENTION window after onset; long-stop must have at least 300 seconds "
            "of observed event time"
        ),
        "selection_order": [
            "validation-normal window FPR within +/-1 percentage point of target 5%",
            "highest minimum of long-stop and backtracking trajectory sensitivity",
            "highest mean of those two sensitivities",
            "shortest minimum decision latency",
            "closest validation-normal FPR to target as the final tie-break",
        ],
        "operational_tradeoff": (
            "Any-window normal trajectory FPR is reported but is not separately "
            "calibrated; it captures repeated-window false-alert accumulation."
        ),
        "candidate_results": candidate_rows,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "window_selection.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    print(json.dumps(select_window(), indent=2))


if __name__ == "__main__":
    main()
