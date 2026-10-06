"""Quality-gated statistical scoring and explainable rule inspection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite

from app.ml.trajectory_anomaly.features import GpsPoint, extract_features
from app.ml.trajectory_anomaly.model import (
    ArtifactValidationError,
    ModelBundle,
    anomaly_scores,
)
from app.ml.trajectory_anomaly.quality import QualityResult, assess_quality
from app.ml.trajectory_anomaly.windows import WINDOW_SECONDS, latest_window

REASON_RULE_CONFIG = {
    "long_stop_seconds": 300.0,
    "high_tortuosity": 3.5,
    "repeated_turn_count": 3,
    "minimum_median_speed_mps": 0.25,
    "maximum_median_speed_mps": 3.0,
}


class TrajectoryAttentionStatus(StrEnum):
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TrajectoryAttentionResult:
    status: TrajectoryAttentionStatus
    score: float | None
    reason_codes: tuple[str, ...]
    model_version: str | None
    quality: QualityResult


def inspect_reason_codes(features: dict[str, float]) -> tuple[str, ...]:
    """Simple readable rules; they do not explain Isolation Forest causality."""
    reasons: list[str] = []
    if features["longest_stop_seconds"] >= REASON_RULE_CONFIG["long_stop_seconds"]:
        reasons.append("LONG_STOP")
    if features["tortuosity"] >= REASON_RULE_CONFIG["high_tortuosity"]:
        reasons.append("HIGH_TORTUOSITY")
    if features["large_turn_count"] >= REASON_RULE_CONFIG["repeated_turn_count"]:
        reasons.append("REPEATED_TURNS")
    if (
        features["median_speed"] > REASON_RULE_CONFIG["maximum_median_speed_mps"]
        or features["median_speed"] < REASON_RULE_CONFIG["minimum_median_speed_mps"]
    ):
        reasons.append("UNUSUAL_MEDIAN_SPEED")
    return tuple(reasons)


def infer_trajectory(
    points: Sequence[GpsPoint],
    bundle: ModelBundle,
    *,
    point_limit_exceeded: bool = False,
) -> TrajectoryAttentionResult:
    window = latest_window(points)
    window_points = window.points
    quality = assess_quality(
        window_points,
        point_limit_exceeded=point_limit_exceeded,
    )
    if not window.complete:
        reasons = tuple(dict.fromkeys((*quality.reason_codes, "INCOMPLETE_WINDOW")))
        quality = replace(quality, valid=False, reason_codes=reasons)
    if not quality.valid:
        return TrajectoryAttentionResult(
            status=TrajectoryAttentionStatus.UNKNOWN,
            score=None,
            reason_codes=quality.reason_codes,
            model_version=str(bundle.metadata.get("model_version", "v2")),
            quality=quality,
        )

    if bundle.metadata.get("window_seconds") != WINDOW_SECONDS:
        raise ArtifactValidationError("artifact window length does not match inference")
    threshold = bundle.metadata.get("threshold")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not isfinite(float(threshold))
    ):
        raise ArtifactValidationError("artifact calibration threshold must be finite")

    features = extract_features(window_points)
    score = anomaly_scores(bundle.model, [features])[0]
    status = (
        TrajectoryAttentionStatus.ATTENTION
        if score > float(threshold)
        else TrajectoryAttentionStatus.NORMAL
    )
    if status == TrajectoryAttentionStatus.ATTENTION:
        reasons = inspect_reason_codes(features)
    else:
        reasons = ()
    return TrajectoryAttentionResult(
        status=status,
        score=score,
        reason_codes=reasons,
        model_version=str(bundle.metadata.get("model_version", "v2")),
        quality=quality,
    )
