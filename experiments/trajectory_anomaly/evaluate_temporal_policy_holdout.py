"""Run the frozen temporal rule once on final normal/stress holdouts."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from experiments.trajectory_anomaly.dataset import (
    BEHAVIORAL_SCENARIOS,
    MIN_EVENT_EVIDENCE_SECONDS,
    RESULTS_DIR,
    DatasetRecord,
    prepare_dataset,
)

from app.ml.trajectory_anomaly.model import ARTIFACT_DIR, anomaly_scores, load_artifact
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS
from app.services.trajectory_temporal import (
    SELECTED_TEMPORAL_POLICY,
    TemporalPolicy,
    alert_episode_count,
    apply_temporal_policy,
)

SELECTION_PATH = RESULTS_DIR / "temporal_policy_selection.json"
FINAL_OUTPUT = RESULTS_DIR / "temporal_policy_frozen_test.json"


def _artifact_sha256() -> str:
    digest = hashlib.sha256()
    with (ARTIFACT_DIR / "isolation_forest.joblib").open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _group_records(
    records: list[DatasetRecord],
) -> dict[str, list[DatasetRecord]]:
    grouped: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        grouped[record.trip.trajectory_id].append(record)
    for trip_records in grouped.values():
        trip_records.sort(key=lambda record: record.window_end)
    return dict(grouped)


def _score_holdout_records(
    records: list[DatasetRecord],
    threshold: float,
    model: Any,
) -> dict[tuple[str, datetime], bool | None]:
    valid = [record for record in records if record.features is not None]
    scores = (
        anomaly_scores(model, [record.features for record in valid])
        if valid
        else []
    )
    flags: dict[tuple[str, datetime], bool | None] = {
        (record.trip.trajectory_id, record.window_end): score > threshold
        for record, score in zip(valid, scores, strict=True)
    }
    for record in records:
        flags.setdefault((record.trip.trajectory_id, record.window_end), None)
    return flags


def _alerts_by_trip(
    records: list[DatasetRecord],
    flags: dict[tuple[str, datetime], bool | None],
    policy: TemporalPolicy,
) -> tuple[
    dict[str, list[DatasetRecord]],
    dict[str, tuple[bool | None, ...]],
]:
    grouped = _group_records(records)
    decisions = {
        trip_id: apply_temporal_policy(
            [flags[(trip_id, record.window_end)] for record in trip_records],
            policy,
        )
        for trip_id, trip_records in grouped.items()
    }
    return grouped, decisions


def _alert_metrics(
    records: list[DatasetRecord],
    flags: dict[tuple[str, datetime], bool | None],
    policy: TemporalPolicy,
) -> dict[str, Any]:
    grouped, decisions = _alerts_by_trip(records, flags, policy)
    trip_alerts = {
        trip_id: any(value is True for value in values)
        for trip_id, values in decisions.items()
    }
    episode_count = sum(alert_episode_count(values) for values in decisions.values())
    valid_flags = [
        flags[(record.trip.trajectory_id, record.window_end)]
        for record in records
        if record.features is not None
    ]
    return {
        "trajectory_count": len(grouped),
        "trajectory_alert_count": sum(trip_alerts.values()),
        "trajectory_alert_rate": sum(trip_alerts.values()) / len(grouped),
        "alert_episode_count": episode_count,
        "alerts_per_trajectory": episode_count / len(grouped),
        "window_count": len(valid_flags),
        "window_level_fpr": sum(value is True for value in valid_flags) / len(valid_flags),
    }


def _event_evidence_available_at(record: DatasetRecord) -> datetime:
    onset = record.trip.behavior_start_seconds or 0.0
    evidence_seconds = MIN_EVENT_EVIDENCE_SECONDS.get(record.trip.scenario, 0.0)
    return record.trip.points[0].timestamp + timedelta(seconds=onset + evidence_seconds)


def _delay_summary(delays: list[float]) -> dict[str, float | int | None]:
    if not delays:
        return {"median_seconds": None, "p90_seconds": None, "detected_count": 0}
    ordered = sorted(delays)
    p90_index = max(0, math.ceil(0.90 * len(ordered)) - 1)
    return {
        "median_seconds": median(ordered),
        "p90_seconds": ordered[p90_index],
        "detected_count": len(ordered),
    }


def _scenario_metrics(
    records: list[DatasetRecord],
    flags: dict[tuple[str, datetime], bool | None],
) -> dict[str, Any]:
    v2_delays: list[float] = []
    v3_delays: list[float] = []
    eligible_valid_windows = 0
    v2_window_hits = 0
    scenario_results: dict[str, Any] = {}
    for scenario in BEHAVIORAL_SCENARIOS:
        scenario_records = [
            record
            for record in records
            if record.trip.scenario == scenario
            and record.split == "stress_test"
        ]
        grouped = _group_records(scenario_records)
        v2_detected = 0
        v3_detected = 0
        v2_scenario_delays: list[float] = []
        v3_scenario_delays: list[float] = []
        for trip_id, trip_records in grouped.items():
            raw_flags = [flags[(trip_id, record.window_end)] for record in trip_records]
            v2_decisions = apply_temporal_policy(raw_flags, TemporalPolicy.SINGLE_WINDOW)
            v3_decisions = apply_temporal_policy(raw_flags, SELECTED_TEMPORAL_POLICY)
            evidence_available = _event_evidence_available_at(trip_records[0])
            eligible_records = [
                (record, raw_flag, v2_decision, v3_decision)
                for record, raw_flag, v2_decision, v3_decision in zip(
                    trip_records,
                    raw_flags,
                    v2_decisions,
                    v3_decisions,
                    strict=True,
                )
                if record.window_end >= evidence_available
            ]
            for record, raw_flag, _, _ in eligible_records:
                if record.features is not None:
                    eligible_valid_windows += 1
                    v2_window_hits += raw_flag is True
            v2_alert_times = [
                record.window_end
                for record, _, decision, _ in eligible_records
                if decision is True
            ]
            v3_alert_times = [
                record.window_end
                for record, _, _, decision in eligible_records
                if decision is True
            ]
            if v2_alert_times:
                v2_detected += 1
                delay = (min(v2_alert_times) - evidence_available).total_seconds()
                v2_scenario_delays.append(delay)
                v2_delays.append(delay)
            if v3_alert_times:
                v3_detected += 1
                delay = (min(v3_alert_times) - evidence_available).total_seconds()
                v3_scenario_delays.append(delay)
                v3_delays.append(delay)
        trajectory_count = len(grouped)
        scenario_results[scenario] = {
            "trajectory_count": trajectory_count,
            "v2_single_window_event_aware_detection_rate": (
                v2_detected / trajectory_count if trajectory_count else None
            ),
            "temporal_v3_event_aware_detection_rate": (
                v3_detected / trajectory_count if trajectory_count else None
            ),
            "v2_detection_delay_from_evidence": _delay_summary(v2_scenario_delays),
            "temporal_v3_detection_delay_from_evidence": _delay_summary(v3_scenario_delays),
        }
    return {
        "event_eligible_window_level_v2_detection_rate": (
            v2_window_hits / eligible_valid_windows if eligible_valid_windows else None
        ),
        "scenarios": scenario_results,
        "pooled_v2_detection_delay_from_evidence": _delay_summary(v2_delays),
        "pooled_temporal_v3_detection_delay_from_evidence": _delay_summary(v3_delays),
    }


def evaluate_frozen_holdout() -> dict[str, Any]:
    if FINAL_OUTPUT.exists():
        raise FileExistsError(
            f"refusing to rerun frozen holdout evaluation: {FINAL_OUTPUT}"
        )
    frozen = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    if not frozen.get("frozen"):
        raise RuntimeError("temporal policy has not been frozen")
    if frozen.get("selected_rule") != SELECTED_TEMPORAL_POLICY.value:
        raise RuntimeError("production temporal policy differs from frozen selection")
    if frozen.get("window_seconds") != WINDOW_SECONDS:
        raise RuntimeError("frozen policy window differs from production window")
    artifact_sha = _artifact_sha256()
    if artifact_sha != frozen.get("artifact_sha256"):
        raise RuntimeError("production artifact changed after temporal policy selection")

    # Holdout is first materialized and scored here, after the policy is frozen.
    all_records = prepare_dataset()
    holdout_records = [
        record
        for record in all_records
        if record.split == "test_normal"
        or (
            record.split == "stress_test"
            and record.trip.scenario in BEHAVIORAL_SCENARIOS
        )
    ]
    test_normal = [record for record in holdout_records if record.split == "test_normal"]
    behavioral_stress = [
        record for record in holdout_records if record.split == "stress_test"
    ]
    bundle = load_artifact()
    threshold = float(bundle.metadata["threshold"])
    flags = _score_holdout_records(
        test_normal + behavioral_stress,
        threshold,
        bundle.model,
    )
    v2_normal = _alert_metrics(test_normal, flags, TemporalPolicy.SINGLE_WINDOW)
    v3_normal = _alert_metrics(test_normal, flags, SELECTED_TEMPORAL_POLICY)
    output = {
        "frozen_policy": frozen["selected_rule"],
        "artifact_sha256": artifact_sha,
        "model_version": bundle.metadata["model_version"],
        "window_seconds": WINDOW_SECONDS,
        "threshold": threshold,
        "holdout_evaluated_at_utc": datetime.now(UTC).isoformat(),
        "holdout_run_count": 1,
        "test_normal": {
            "v2_single_window": v2_normal,
            "temporal_v3": v3_normal,
        },
        "behavioral_stress": _scenario_metrics(behavioral_stress, flags),
        "method_notes": [
            "No IF fitting, threshold changes, or candidate-policy selection occurred in this run.",
            "All candidates were scored and selected before this final test/stress pass.",
            (
                "Window-level FPR is a property of unchanged V2 scores and is "
                "therefore the same for V2 and V3."
            ),
            "Temporal V3 changes product ATTENTION aggregation only; it does not add ML features.",
            "Stress detection and delays are measured from scenario event-evidence availability.",
        ],
    }
    FINAL_OUTPUT.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> None:
    result = evaluate_frozen_holdout()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
