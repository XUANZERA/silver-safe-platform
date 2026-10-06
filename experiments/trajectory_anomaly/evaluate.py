"""Trajectory-level, multi-seed evaluation and plots for synthetic stress cases."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sklearn.metrics
from experiments.trajectory_anomaly.dataset import (
    RESULTS_DIR,
    DatasetRecord,
    feature_rows,
    is_post_event_window,
    prepare_dataset,
    records_in,
    write_dataset_summary,
)
from experiments.trajectory_anomaly.simulate import ANOMALY_SCENARIOS, NORMAL_SCENARIOS

from app.ml.trajectory_anomaly.features import FEATURE_NAMES
from app.ml.trajectory_anomaly.inference import REASON_RULE_CONFIG
from app.ml.trajectory_anomaly.model import (
    TARGET_VALIDATION_FPR,
    anomaly_scores,
    calibrate_threshold,
    fit_model,
)
from app.ml.trajectory_anomaly.windows import (
    WINDOW_DEFINITION,
    WINDOW_MINIMUM_COVERAGE_RATIO,
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
)

SEEDS = (42, 43, 44, 45, 46)
BEHAVIORAL_SCENARIOS = (
    "long_stop",
    "repeated_backtracking",
    "circular_wandering",
    "abnormal_speed_pattern",
)
QUALITY_SCENARIOS = ("gps_dropout", "poor_accuracy", "severe_timestamp_gap")


def rule_attention(features: dict[str, float]) -> bool:
    """Transparent comparator with three fixed, uncalibrated rules."""
    return (
        features["longest_stop_seconds"] >= REASON_RULE_CONFIG["long_stop_seconds"]
        or features["tortuosity"] >= REASON_RULE_CONFIG["high_tortuosity"]
        or features["large_turn_count"] >= REASON_RULE_CONFIG["repeated_turn_count"]
    )


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _any_window_trip_rate(records: list[DatasetRecord], predictions: list[bool]) -> float | None:
    by_trip: dict[str, bool] = defaultdict(bool)
    for record, prediction in zip(records, predictions, strict=True):
        by_trip[record.trip.trajectory_id] |= prediction
    return _rate(sum(by_trip.values()), len(by_trip))


def _scores_for_records(model, threshold: float, records: list[DatasetRecord]):
    valid = [record for record in records if record.quality.valid and record.features is not None]
    scores = anomaly_scores(model, [record.features for record in valid]) if valid else []
    return valid, scores, [score > threshold for score in scores]


def _plot_scores(score_sets: dict[str, list[float]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    for label, values in score_sets.items():
        if values:
            ax.hist(values, bins=24, alpha=0.45, density=True, label=f"{label} (n={len(values)})")
    ax.set_xlabel("Anomaly score (higher = more abnormal)")
    ax.set_ylabel("Density")
    ax.set_title("Synthetic test score distributions")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_features(records: list[DatasetRecord], path: Path) -> None:
    scenarios = [
        scenario
        for scenario in NORMAL_SCENARIOS + ANOMALY_SCENARIOS
        if any(record.trip.scenario == scenario and record.features for record in records)
    ]
    fig, axes = plt.subplots(2, 5, figsize=(18, 9))
    for axis, feature in zip(axes.flat, FEATURE_NAMES, strict=True):
        groups = [
            [
                record.features[feature]
                for record in records
                if record.trip.scenario == scenario and record.features is not None
            ]
            for scenario in scenarios
        ]
        axis.boxplot(groups, showfliers=False)
        axis.set_title(feature)
        axis.set_xticks(range(1, len(scenarios) + 1), scenarios, rotation=75, ha="right")
        axis.grid(axis="y", alpha=0.25)
    fig.suptitle("Feature distributions by synthetic scenario (quality-valid trips)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def evaluate(records: list[DatasetRecord], results_dir: Path = RESULTS_DIR) -> dict[str, object]:
    results_dir.mkdir(parents=True, exist_ok=True)
    train_normal = feature_rows(records, "train_normal")
    validation_normal = feature_rows(records, "validation_normal")
    validation_records = [
        record
        for record in records
        if record.split == "validation_normal" and record.features is not None
    ]
    test_records = records_in(records, "test_normal")
    test_normal = [record for record in test_records if record.features]
    if len(train_normal) == 0 or len(validation_normal) == 0 or len(test_normal) == 0:
        raise RuntimeError("train, validation, and test normal sets must be non-empty")

    fold_rows: list[dict[str, object]] = []
    seed_rows: list[dict[str, object]] = []
    detection_rates: dict[str, list[float]] = defaultdict(list)
    any_window_detection_rates: dict[str, list[float]] = defaultdict(list)
    window_detection_rates: dict[str, list[float]] = defaultdict(list)
    post_event_window_rates: dict[str, list[float]] = defaultdict(list)
    normal_rates: dict[str, list[float]] = defaultdict(list)
    normal_trip_rates: dict[str, list[float]] = defaultdict(list)
    seed42_scores: dict[str, list[float]] = {}
    primary_by_scenario: dict[str, dict[str, object]] = {}

    for seed in SEEDS:
        model = fit_model(train_normal, random_state=seed)
        threshold = calibrate_threshold(
            model,
            validation_normal,
            target_fpr=TARGET_VALIDATION_FPR,
        )
        validation_scores = anomaly_scores(model, validation_normal)
        validation_fpr = sum(score > threshold for score in validation_scores) / len(
            validation_scores
        )
        validation_predictions = [score > threshold for score in validation_scores]
        validation_trip_fpr = _any_window_trip_rate(
            validation_records,
            validation_predictions,
        )
        test_valid, test_scores, test_predictions = _scores_for_records(
            model, threshold, test_records
        )
        test_fpr = _rate(sum(test_predictions), len(test_predictions)) or 0.0
        test_trip_fpr = _any_window_trip_rate(test_valid, test_predictions) or 0.0
        test_rules = [rule_attention(record.features) for record in test_valid]
        seed_result: dict[str, object] = {
            "seed": seed,
            "threshold": threshold,
            "validation_normal_fpr": validation_fpr,
            "validation_normal_any_window_trip_fpr": validation_trip_fpr,
            "test_normal_fpr": test_fpr,
            "test_normal_any_window_trip_fpr": test_trip_fpr,
            "test_normal_rule_fpr": _rate(sum(test_rules), len(test_rules)),
        }
        fold_rows.append(
            {
                "seed": seed,
                "split": "validation_normal",
                "scenario": "all_normal",
                "trajectory_count": len(
                    {record.trip.trajectory_id for record in validation_records}
                ),
                "window_count": len(validation_normal),
                "quality_valid_count": len(validation_normal),
                "quality_unknown_rate": 0.0,
                "if_attention_rate": validation_fpr,
                "rule_attention_rate": _rate(
                    sum(
                        rule_attention(record.features)
                        for record in records_in(records, "validation_normal")
                    ),
                    len(validation_normal),
                ),
                "threshold": threshold,
            }
        )
        for scenario in NORMAL_SCENARIOS:
            scenario_normal = [
                record for record in test_records if record.trip.scenario == scenario
            ]
            scenario_valid, _, scenario_predictions = _scores_for_records(
                model,
                threshold,
                scenario_normal,
            )
            scenario_fpr = _rate(sum(scenario_predictions), len(scenario_predictions)) or 0.0
            scenario_trip_fpr = _any_window_trip_rate(scenario_valid, scenario_predictions) or 0.0
            normal_rates[scenario].append(scenario_fpr)
            normal_trip_rates[scenario].append(scenario_trip_fpr)
            seed_result[f"{scenario}_test_fpr"] = scenario_fpr
            seed_result[f"{scenario}_test_any_window_trip_fpr"] = scenario_trip_fpr
        fold_rows.append(
            {
                "seed": seed,
                "split": "test_normal",
                "scenario": "all_normal",
                "trajectory_count": len({record.trip.trajectory_id for record in test_records}),
                "window_count": len(test_records),
                "quality_valid_count": len(test_valid),
                "quality_unknown_rate": 1 - len(test_valid) / len(test_records),
                "if_attention_rate": test_fpr,
                "rule_attention_rate": _rate(sum(test_rules), len(test_rules)),
                "threshold": threshold,
            }
        )

        all_binary_labels = [0] * len(test_normal)
        all_binary_scores = list(anomaly_scores(model, [record.features for record in test_normal]))
        for scenario in BEHAVIORAL_SCENARIOS:
            scenario_records = [
                record
                for record in records
                if record.trip.scenario == scenario and record.split == "stress_test"
            ]
            valid, scores, predictions = _scores_for_records(model, threshold, scenario_records)
            rate = _rate(sum(predictions), len(predictions))
            trip_rate_any_window = _any_window_trip_rate(valid, predictions)
            eligible_pairs = [
                (record, prediction)
                for record, prediction in zip(valid, predictions, strict=True)
                if is_post_event_window(record)
            ]
            eligible_records = [record for record, _ in eligible_pairs]
            eligible_predictions = [prediction for _, prediction in eligible_pairs]
            event_aware_trip_rate = _any_window_trip_rate(
                eligible_records,
                eligible_predictions,
            )
            post_event_window_rate = _rate(
                sum(eligible_predictions),
                len(eligible_predictions),
            )
            detection_rates[scenario].append(event_aware_trip_rate or 0.0)
            any_window_detection_rates[scenario].append(
                trip_rate_any_window or 0.0
            )
            window_detection_rates[scenario].append(rate or 0.0)
            post_event_window_rates[scenario].append(post_event_window_rate or 0.0)
            seed_result[f"{scenario}_detection_rate"] = event_aware_trip_rate
            seed_result[f"{scenario}_any_window_detection_rate"] = trip_rate_any_window
            seed_result[f"{scenario}_window_detection_rate"] = rate
            seed_result[f"{scenario}_post_event_window_detection_rate"] = post_event_window_rate
            rule_rate = _rate(sum(rule_attention(record.features) for record in valid), len(valid))
            fold_rows.append(
                {
                    "seed": seed,
                    "split": "stress_test",
                    "scenario": scenario,
                    "trajectory_count": len(
                        {record.trip.trajectory_id for record in scenario_records}
                    ),
                    "window_count": len(scenario_records),
                    "quality_valid_count": len(valid),
                    "quality_unknown_rate": 1 - len(valid) / len(scenario_records),
                    "if_attention_rate": event_aware_trip_rate,
                    "if_any_window_trip_detection_rate": trip_rate_any_window,
                    "if_window_attention_rate": rate,
                    "if_post_event_window_attention_rate": post_event_window_rate,
                    "rule_attention_rate": rule_rate,
                    "threshold": threshold,
                }
            )
            if seed == 42:
                seed42_scores[scenario] = scores
                primary_by_scenario[scenario] = {
                    "if_window_detection_rate_seed42": rate,
                    "if_detection_rate_seed42": event_aware_trip_rate,
                    "if_any_window_detection_rate_seed42": trip_rate_any_window,
                    "if_post_event_window_detection_rate_seed42": post_event_window_rate,
                    "rule_detection_rate": rule_rate,
                    "valid_count": len(valid),
                    "unknown_count": len(scenario_records) - len(valid),
                }
            all_binary_labels.extend([1] * len(valid))
            all_binary_scores.extend(scores)

        for scenario in QUALITY_SCENARIOS + ("gps_jump",):
            scenario_records = [
                record
                for record in records
                if record.trip.scenario == scenario and record.split == "stress_test"
            ]
            valid, _, predictions = _scores_for_records(model, threshold, scenario_records)
            unknown_rate = 1 - len(valid) / len(scenario_records) if scenario_records else None
            seed_result[f"{scenario}_unknown_rate"] = unknown_rate
            if scenario == "gps_jump":
                gps_jump_rate = _rate(sum(predictions), len(predictions))
                gps_jump_trip_rate = _any_window_trip_rate(valid, predictions)
                seed_result["gps_jump_detection_rate_when_valid"] = gps_jump_rate
                seed_result["gps_jump_trajectory_detection_rate_when_valid"] = gps_jump_trip_rate
                if gps_jump_trip_rate is not None:
                    detection_rates[scenario].append(gps_jump_trip_rate)
                if gps_jump_rate is not None:
                    window_detection_rates[scenario].append(gps_jump_rate)
            fold_rows.append(
                {
                    "seed": seed,
                    "split": "stress_test",
                    "scenario": scenario,
                    "trajectory_count": len(
                        {record.trip.trajectory_id for record in scenario_records}
                    ),
                    "window_count": len(scenario_records),
                    "quality_valid_count": len(valid),
                    "quality_unknown_rate": unknown_rate,
                    "if_attention_rate": _rate(sum(predictions), len(predictions)),
                    "rule_attention_rate": _rate(
                        sum(rule_attention(record.features) for record in valid), len(valid)
                    ),
                    "threshold": threshold,
                }
            )
            if seed == 42:
                valid_records = [record for record in scenario_records if record.quality.valid]
                primary_by_scenario[scenario] = {
                    "if_detection_rate_seed42": _any_window_trip_rate(valid, predictions),
                    "if_window_detection_rate_seed42": _rate(
                        sum(predictions), len(predictions)
                    ),
                    "if_trajectory_detection_rate_seed42": _any_window_trip_rate(
                        valid,
                        predictions,
                    ),
                    "rule_detection_rate": _rate(
                        sum(rule_attention(record.features) for record in valid_records),
                        len(valid_records),
                    ),
                    "valid_count": len(valid),
                    "unknown_count": len(scenario_records) - len(valid),
                }

        if len(set(all_binary_labels)) == 2:
            seed_result["behavioral_stress_auroc"] = sklearn.metrics.roc_auc_score(
                all_binary_labels, all_binary_scores
            )
            seed_result["behavioral_stress_auprc"] = sklearn.metrics.average_precision_score(
                all_binary_labels, all_binary_scores
            )
        seed_rows.append(seed_result)

    scenario_rows: list[dict[str, object]] = []
    for scenario in NORMAL_SCENARIOS:
        normal_records = [
            record
            for record in records
            if record.trip.scenario == scenario and record.split == "test_normal"
        ]
        model_fprs = normal_rates[scenario]
        rule_fprs = [rule_attention(record.features) for record in normal_records]
        scenario_rows.append(
            {
                "scenario": scenario,
                "split": "test_normal",
                "quality_valid_count": len(normal_records),
                "window_count": len(normal_records),
                "trajectory_count": len({record.trip.trajectory_id for record in normal_records}),
                "quality_unknown_rate": 0.0,
                "rule_attention_rate": _rate(sum(rule_fprs), len(rule_fprs)),
                "if_attention_rate_seed42": model_fprs[0],
                "if_attention_rate_mean_5seeds": sum(model_fprs) / len(model_fprs),
                "if_attention_rate_std_5seeds": math.sqrt(
                    sum((value - sum(model_fprs) / len(model_fprs)) ** 2 for value in model_fprs)
                    / len(model_fprs)
                ),
                "if_any_window_trip_fpr_seed42": normal_trip_rates[scenario][0],
                "if_any_window_trip_fpr_mean_5seeds": sum(normal_trip_rates[scenario])
                / len(normal_trip_rates[scenario]),
            }
        )
    for scenario in ANOMALY_SCENARIOS:
        details = primary_by_scenario[scenario]
        rates = detection_rates.get(scenario, [])
        mean_rate = sum(rates) / len(rates) if rates else None
        scenario_rows.append(
            {
                "scenario": scenario,
                "split": "stress_test",
                "quality_valid_count": details["valid_count"],
                "quality_unknown_rate": _rate(
                    details["unknown_count"],
                    details["unknown_count"] + details["valid_count"],
                ),
                "rule_attention_rate": details["rule_detection_rate"],
                "if_attention_rate_seed42": details["if_detection_rate_seed42"],
                "if_any_window_detection_rate_seed42": details.get(
                    "if_any_window_detection_rate_seed42"
                ),
                "if_window_detection_rate_seed42": details.get("if_window_detection_rate_seed42"),
                "if_post_event_window_detection_rate_seed42": details.get(
                    "if_post_event_window_detection_rate_seed42"
                ),
                "if_attention_rate_mean_5seeds": mean_rate,
                "if_attention_rate_std_5seeds": (
                    math.sqrt(sum((value - mean_rate) ** 2 for value in rates) / len(rates))
                    if rates and mean_rate is not None
                    else None
                ),
                "if_window_detection_rate_mean_5seeds": (
                    sum(window_detection_rates[scenario]) / len(window_detection_rates[scenario])
                    if window_detection_rates.get(scenario)
                    else None
                ),
                "if_any_window_detection_rate_mean_5seeds": (
                    sum(any_window_detection_rates[scenario])
                    / len(any_window_detection_rates[scenario])
                    if any_window_detection_rates.get(scenario)
                    else None
                ),
                "if_post_event_window_detection_rate_mean_5seeds": (
                    sum(post_event_window_rates[scenario])
                    / len(post_event_window_rates[scenario])
                    if post_event_window_rates.get(scenario)
                    else None
                ),
            }
        )

    _write_rows(results_dir / "fold_metrics.csv", fold_rows)
    _write_rows(results_dir / "scenario_metrics.csv", scenario_rows)
    _write_rows(results_dir / "seed_metrics.csv", seed_rows)

    primary_model = fit_model(train_normal, random_state=42)
    primary_threshold = calibrate_threshold(primary_model, validation_normal)
    score_sets = {
        "test_normal": anomaly_scores(primary_model, [record.features for record in test_normal])
    }
    score_sets.update(seed42_scores)
    _plot_scores(score_sets, results_dir / "score_distribution.png")
    _plot_features(records, results_dir / "feature_distributions" / "by_scenario.png")
    write_dataset_summary(records, results_dir)

    validation_fpr = seed_rows[0]["validation_normal_fpr"]
    test_fpr = seed_rows[0]["test_normal_fpr"]
    summary: dict[str, object] = {
        "task": "fixed-window statistical trajectory anomaly detection",
        "allowed_statuses": ["NORMAL", "ATTENTION", "UNKNOWN"],
        "window_seconds": WINDOW_SECONDS,
        "window_definition": WINDOW_DEFINITION,
        "window_step_seconds": WINDOW_STEP_SECONDS,
        "window_minimum_coverage_ratio": WINDOW_MINIMUM_COVERAGE_RATIO,
        "normal_false_positive_rate_seed42_test": test_fpr,
        "normal_false_positive_rate_seed42_validation": validation_fpr,
        "target_validation_fpr": TARGET_VALIDATION_FPR,
        "validation_threshold_seed42": primary_threshold,
        "normal_trip_split_counts": {
            "train_normal_trajectories": len(
                {record.trip.trajectory_id for record in records if record.split == "train_normal"}
            ),
            "validation_normal_trajectories": len(
                {record.trip.trajectory_id for record in validation_records}
            ),
            "test_normal_trajectories": len(
                {record.trip.trajectory_id for record in test_records}
            ),
        },
        "normal_window_counts": {
            "train_normal": len(train_normal),
            "validation_normal": len(validation_normal),
            "test_normal": len(test_normal),
        },
        "stress_trip_count": len(
            {record.trip.trajectory_id for record in records if record.split == "stress_test"}
        ),
        "stress_window_count": sum(record.split == "stress_test" for record in records),
        "behavioral_synthetic_stress_auroc_seed42": seed_rows[0].get("behavioral_stress_auroc"),
        "behavioral_synthetic_stress_auprc_seed42": seed_rows[0].get("behavioral_stress_auprc"),
        "seed_metrics": seed_rows,
        "method_notes": [
            "Only synthetic normal training trajectories are used for fitting.",
            (
                "Trajectory IDs are split before 60-second sliding-window extraction; "
                "overlapping windows from one trip remain in one split."
            ),
            (
                "Development anomaly trajectories are separate from the final "
                "stress-test trajectories."
            ),
            (
                "Per-window FPR is reported alongside per-trajectory any-window "
                "FPR to expose repeated-query accumulation."
            ),
            "Validation normal alone calibrates the score threshold; stress cases do not tune it.",
            "No scaler is used because Isolation Forest partitions random feature dimensions.",
            (
                "AUROC/AUPRC indicate synthetic stress-test discrimination only, "
                "not real-world safety performance."
            ),
        ],
    }
    (results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def evaluate_dataset_seed_stability(
    dataset_seeds: tuple[int, ...] = SEEDS,
) -> dict[str, object]:
    """Hold IF seed fixed and vary only synthetic dataset generation seed."""
    rows: list[dict[str, object]] = []
    for dataset_seed in dataset_seeds:
        records = prepare_dataset(seed=dataset_seed)
        train_rows = feature_rows(records, "train_normal")
        validation_rows = feature_rows(records, "validation_normal")
        test_records = records_in(records, "test_normal")
        model = fit_model(train_rows, random_state=42)
        threshold = calibrate_threshold(model, validation_rows)
        test_valid, test_scores, test_predictions = _scores_for_records(
            model,
            threshold,
            test_records,
        )
        row: dict[str, object] = {
            "dataset_seed": dataset_seed,
            "model_seed": 42,
            "threshold": threshold,
            "test_normal_window_fpr": _rate(sum(test_predictions), len(test_predictions)),
            "test_normal_any_window_trip_fpr": _any_window_trip_rate(
                test_valid,
                test_predictions,
            ),
        }
        for scenario in BEHAVIORAL_SCENARIOS:
            scenario_records = [
                record
                for record in records
                if record.split == "stress_test" and record.trip.scenario == scenario
            ]
            valid, _, predictions = _scores_for_records(model, threshold, scenario_records)
            eligible_pairs = [
                (record, prediction)
                for record, prediction in zip(valid, predictions, strict=True)
                if is_post_event_window(record)
            ]
            eligible_records = [record for record, _ in eligible_pairs]
            eligible_predictions = [prediction for _, prediction in eligible_pairs]
            row[f"{scenario}_window_detection_rate"] = _rate(sum(predictions), len(predictions))
            row[f"{scenario}_trajectory_detection_rate"] = _any_window_trip_rate(
                eligible_records,
                eligible_predictions,
            )
            row[f"{scenario}_any_window_trajectory_detection_rate"] = (
                _any_window_trip_rate(valid, predictions)
            )
        rows.append(row)

    metric_fields = [
        "test_normal_window_fpr",
        "test_normal_any_window_trip_fpr",
        *(
            f"{scenario}_trajectory_detection_rate"
            for scenario in BEHAVIORAL_SCENARIOS
        ),
    ]
    aggregates: dict[str, dict[str, float | None]] = {}
    for field in metric_fields:
        values = [float(row[field]) for row in rows if row[field] is not None]
        mean_value = sum(values) / len(values) if values else None
        aggregates[field] = {
            "mean": mean_value,
            "std": (
                math.sqrt(sum((value - mean_value) ** 2 for value in values) / len(values))
                if values and mean_value is not None
                else None
            ),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }

    result: dict[str, object] = {
        "fixed_model_random_state": 42,
        "dataset_seeds": list(dataset_seeds),
        "window_seconds": WINDOW_SECONDS,
        "seed_metrics": rows,
        "aggregates": aggregates,
    }
    (RESULTS_DIR / "dataset_seed_stability.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    summary_path = RESULTS_DIR / "summary.json"
    previous_summary = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if summary_path.exists()
        else {}
    )
    records = prepare_dataset()
    write_dataset_summary(records, RESULTS_DIR)
    summary = evaluate(records)
    if "final_production_artifact_test" in previous_summary:
        summary["final_production_artifact_test"] = previous_summary[
            "final_production_artifact_test"
        ]
    summary["dataset_seed_stability"] = evaluate_dataset_seed_stability()
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
