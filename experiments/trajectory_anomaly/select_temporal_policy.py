"""Select and freeze one product-level temporal rule on development data only."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
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
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS, WINDOW_STEP_SECONDS
from app.services.trajectory_temporal import (
    TemporalPolicy,
    alert_episode_count,
    apply_temporal_policy,
)

MINIMUM_VALIDATION_ALERT_RATE_REDUCTION = 0.05
MCNEMAR_ONE_SIDED_ALPHA = 0.05
POLICY_COMPLEXITY_ORDER = {
    TemporalPolicy.TWO_CONSECUTIVE: 0,
    TemporalPolicy.TWO_OF_THREE: 1,
    TemporalPolicy.THREE_OF_FIVE: 2,
}
SELECTION_OUTPUT = RESULTS_DIR / "temporal_policy_selection.json"
PROTOCOL_PATH = RESULTS_DIR / "temporal_policy_protocol.json"


def _group_records(
    records: list[DatasetRecord],
) -> dict[str, list[DatasetRecord]]:
    grouped: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        grouped[record.trip.trajectory_id].append(record)
    for trip_records in grouped.values():
        trip_records.sort(key=lambda record: record.window_end)
    return dict(grouped)


def _score_flags(
    records: list[DatasetRecord],
    bundle: Any,
) -> dict[tuple[str, object], bool | None]:
    """Score only the supplied allowed-split records with the frozen V2 artifact."""
    threshold = float(bundle.metadata["threshold"])
    valid_records = [record for record in records if record.features is not None]
    scores = anomaly_scores(
        bundle.model,
        [record.features for record in valid_records],
    )
    keyed: dict[tuple[str, object], bool | None] = {
        (record.trip.trajectory_id, record.window_end): score > threshold
        for record, score in zip(valid_records, scores, strict=True)
    }
    for record in records:
        keyed.setdefault((record.trip.trajectory_id, record.window_end), None)
    return keyed


def _decisions_by_trip(
    records: list[DatasetRecord],
    flags: dict[tuple[str, object], bool | None],
    policy: TemporalPolicy,
) -> tuple[dict[str, list[DatasetRecord]], dict[str, tuple[bool | None, ...]]]:
    grouped = _group_records(records)
    decisions = {
        trip_id: apply_temporal_policy(
            [flags[(trip_id, record.window_end)] for record in trip_records],
            policy,
        )
        for trip_id, trip_records in grouped.items()
    }
    return grouped, decisions


def _validation_normal_metrics(
    records: list[DatasetRecord],
    flags: dict[tuple[str, object], bool | None],
    policy: TemporalPolicy,
) -> dict[str, Any]:
    grouped, decisions = _decisions_by_trip(records, flags, policy)
    valid_flags = [
        flags[(record.trip.trajectory_id, record.window_end)]
        for record in records
        if record.features is not None
    ]
    trip_alerts = {
        trip_id: any(decision is True for decision in trip_decisions)
        for trip_id, trip_decisions in decisions.items()
    }
    episode_count = sum(
        alert_episode_count(trip_decisions) for trip_decisions in decisions.values()
    )
    trip_count = len(grouped)
    return {
        "window_count": len(valid_flags),
        "window_level_fpr": sum(value is True for value in valid_flags) / len(valid_flags),
        "trajectory_count": trip_count,
        "trajectory_level_alert_count": sum(trip_alerts.values()),
        "trajectory_level_alert_rate": sum(trip_alerts.values()) / trip_count,
        "alert_episode_count": episode_count,
        "alerts_per_trajectory": episode_count / trip_count,
    }


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _event_evidence_available_at(record: DatasetRecord) -> datetime:
    onset = record.trip.behavior_start_seconds or 0.0
    evidence_seconds = MIN_EVENT_EVIDENCE_SECONDS.get(record.trip.scenario, 0.0)
    return record.trip.points[0].timestamp + timedelta(seconds=onset + evidence_seconds)


def _development_metrics(
    records: list[DatasetRecord],
    flags: dict[tuple[str, object], bool | None],
    policy: TemporalPolicy,
) -> dict[str, Any]:
    scenario_results: dict[str, Any] = {}
    all_detected_delays: list[float] = []
    scenario_detection_rates: list[float] = []
    for scenario in BEHAVIORAL_SCENARIOS:
        scenario_records = [
            record
            for record in records
            if record.trip.scenario == scenario and record.split == "development_anomaly"
        ]
        grouped, decisions = _decisions_by_trip(scenario_records, flags, policy)
        detected = 0
        delays: list[float] = []
        for trip_id, trip_records in grouped.items():
            product_decisions = decisions[trip_id]
            evidence_available = _event_evidence_available_at(trip_records[0])
            eligible_alert_times = [
                record.window_end
                for record, decision in zip(trip_records, product_decisions, strict=True)
                if decision is True and record.window_end >= evidence_available
            ]
            if eligible_alert_times:
                detected += 1
                delays.append(
                    (min(eligible_alert_times) - evidence_available).total_seconds()
                )
        trajectory_count = len(grouped)
        detection_rate = detected / trajectory_count if trajectory_count else 0.0
        scenario_detection_rates.append(detection_rate)
        all_detected_delays.extend(delays)
        scenario_results[scenario] = {
            "trajectory_count": trajectory_count,
            "detected_trajectory_count": detected,
            "trajectory_detection_rate": detection_rate,
            "median_detection_delay_seconds_from_evidence": median(delays) if delays else None,
            "p90_detection_delay_seconds_from_evidence": _percentile(delays, 0.90),
        }
    return {
        "scenarios": scenario_results,
        "macro_trajectory_detection_rate": (
            sum(scenario_detection_rates) / len(scenario_detection_rates)
        ),
        "median_detection_delay_seconds_from_evidence": (
            median(all_detected_delays) if all_detected_delays else None
        ),
        "p90_detection_delay_seconds_from_evidence": _percentile(
            all_detected_delays,
            0.90,
        ),
        "detected_trajectory_count": len(all_detected_delays),
    }


def _one_sided_exact_mcnemar_p(
    baseline: dict[str, bool],
    candidate: dict[str, bool],
) -> float:
    baseline_only = sum(
        baseline[trip_id] and not candidate[trip_id]
        for trip_id in baseline
    )
    candidate_only = sum(
        candidate[trip_id] and not baseline[trip_id]
        for trip_id in baseline
    )
    discordant = baseline_only + candidate_only
    if discordant == 0 or baseline_only <= candidate_only:
        return 1.0
    return sum(math.comb(discordant, k) for k in range(baseline_only, discordant + 1)) / (
        2**discordant
    )


def _artifact_sha256() -> str:
    digest = hashlib.sha256()
    with (ARTIFACT_DIR / "isolation_forest.joblib").open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_predeclared_protocol() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    candidate_ids = [candidate["id"] for candidate in protocol["candidates"]]
    if candidate_ids != [policy.value for policy in TemporalPolicy]:
        raise RuntimeError("temporal candidate list differs from the predeclared protocol")
    gate = protocol["validation_alert_reduction_gate"]
    if (
        gate["minimum_absolute_trajectory_alert_rate_reduction"]
        != MINIMUM_VALIDATION_ALERT_RATE_REDUCTION
        or gate["alpha"] != MCNEMAR_ONE_SIDED_ALPHA
        or gate["paired_test"] != "one-sided exact McNemar against A"
    ):
        raise RuntimeError("selection code differs from the predeclared validation gate")
    if protocol["temporal_semantics"]["sampling_cadence_seconds"] != WINDOW_STEP_SECONDS:
        raise RuntimeError("predeclared cadence differs from the frozen V2 window cadence")
    return protocol


def select_policy(records: list[DatasetRecord]) -> dict[str, Any]:
    protocol = _validate_predeclared_protocol()
    allowed_splits = {"train_normal", "validation_normal", "development_anomaly"}
    observed_splits = {record.split for record in records}
    if observed_splits - allowed_splits:
        raise RuntimeError(f"selection data includes disallowed splits: {observed_splits}")

    validation_records = [record for record in records if record.split == "validation_normal"]
    development_records = [
        record
        for record in records
        if record.split == "development_anomaly"
        and record.trip.scenario in BEHAVIORAL_SCENARIOS
    ]
    if not validation_records or not development_records:
        raise RuntimeError("validation normal and development anomaly data are required")

    bundle = load_artifact()
    if bundle.metadata.get("window_seconds") != WINDOW_SECONDS:
        raise RuntimeError("loaded production artifact does not use the frozen V2 window")
    selection_records = validation_records + development_records
    flags = _score_flags(selection_records, bundle)
    validation_grouped = _group_records(validation_records)
    metrics: dict[TemporalPolicy, dict[str, Any]] = {}
    alert_by_policy: dict[TemporalPolicy, dict[str, bool]] = {}
    for policy in TemporalPolicy:
        normal_metrics = _validation_normal_metrics(validation_records, flags, policy)
        development_metrics = _development_metrics(development_records, flags, policy)
        metrics[policy] = {
            "validation_normal": normal_metrics,
            "development_behavioral_anomaly": development_metrics,
        }
        _, decisions = _decisions_by_trip(validation_records, flags, policy)
        alert_by_policy[policy] = {
            trip_id: any(value is True for value in decisions[trip_id])
            for trip_id in validation_grouped
        }

    baseline = TemporalPolicy.SINGLE_WINDOW
    baseline_rate = metrics[baseline]["validation_normal"]["trajectory_level_alert_rate"]
    eligibility: dict[str, Any] = {}
    eligible_policies: list[TemporalPolicy] = []
    for policy in (
        TemporalPolicy.TWO_CONSECUTIVE,
        TemporalPolicy.TWO_OF_THREE,
        TemporalPolicy.THREE_OF_FIVE,
    ):
        candidate_rate = metrics[policy]["validation_normal"]["trajectory_level_alert_rate"]
        reduction = baseline_rate - candidate_rate
        p_value = _one_sided_exact_mcnemar_p(
            alert_by_policy[baseline],
            alert_by_policy[policy],
        )
        eligible = (
            reduction >= MINIMUM_VALIDATION_ALERT_RATE_REDUCTION
            and p_value < MCNEMAR_ONE_SIDED_ALPHA
        )
        eligibility[policy.value] = {
            "absolute_trajectory_alert_rate_reduction": reduction,
            "minimum_required_reduction": MINIMUM_VALIDATION_ALERT_RATE_REDUCTION,
            "paired_one_sided_exact_mcnemar_p": p_value,
            "alpha": MCNEMAR_ONE_SIDED_ALPHA,
            "eligible": eligible,
        }
        if eligible:
            eligible_policies.append(policy)

    selected: TemporalPolicy | None = None
    if eligible_policies:
        highest_detection = max(
            metrics[policy]["development_behavioral_anomaly"][
                "macro_trajectory_detection_rate"
            ]
            for policy in eligible_policies
        )
        finalists = [
            policy
            for policy in eligible_policies
            if math.isclose(
                metrics[policy]["development_behavioral_anomaly"][
                    "macro_trajectory_detection_rate"
                ],
                highest_detection,
                abs_tol=1e-12,
            )
        ]
        shortest_median_delay = min(
            metrics[policy]["development_behavioral_anomaly"][
                "median_detection_delay_seconds_from_evidence"
            ]
            if metrics[policy]["development_behavioral_anomaly"][
                "median_detection_delay_seconds_from_evidence"
            ]
            is not None
            else math.inf
            for policy in finalists
        )
        finalists = [
            policy
            for policy in finalists
            if math.isclose(
                metrics[policy]["development_behavioral_anomaly"][
                    "median_detection_delay_seconds_from_evidence"
                ]
                if metrics[policy]["development_behavioral_anomaly"][
                    "median_detection_delay_seconds_from_evidence"
                ]
                is not None
                else math.inf,
                shortest_median_delay,
                abs_tol=1e-12,
            )
        ]
        selected = min(finalists, key=lambda policy: POLICY_COMPLEXITY_ORDER[policy])

    return {
        "selection_status": "frozen" if selected is not None else "no_eligible_policy",
        "selected_rule": selected.value if selected is not None else None,
        "frozen": selected is not None,
        "artifact_sha256": _artifact_sha256(),
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "window_seconds": bundle.metadata["window_seconds"],
        "window_step_seconds": WINDOW_STEP_SECONDS,
        "selection_data_splits": [
            "train_normal",
            "validation_normal",
            "development_anomaly",
        ],
        "scored_selection_splits": ["validation_normal", "development_anomaly"],
        "excluded_before_freeze": ["test_normal", "stress_test"],
        "behavioral_scenarios": list(BEHAVIORAL_SCENARIOS),
        "selection_protocol": protocol,
        "eligibility": eligibility,
        "candidate_results": {policy.value: metrics[policy] for policy in TemporalPolicy},
    }


def main() -> None:
    if SELECTION_OUTPUT.exists():
        raise FileExistsError(
            f"refusing to overwrite frozen selection output: {SELECTION_OUTPUT}"
        )
    _validate_predeclared_protocol()
    records = prepare_dataset(selection_only=True)
    result = select_policy(records)
    SELECTION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    if not result["frozen"]:
        raise RuntimeError(
            "no candidate met the predeclared validation alert-reduction condition; "
            "no policy was frozen and no holdout was evaluated"
        )


if __name__ == "__main__":
    main()
