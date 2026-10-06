"""Shared fixed elapsed-time windows for training and production inference."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.ml.trajectory_anomaly.features import GpsPoint

WINDOW_SECONDS = 10 * 60
WINDOW_STEP_SECONDS = 60
WINDOW_MINIMUM_COVERAGE_RATIO = 0.9
WINDOW_DEFINITION = "trailing_elapsed_time; inclusive observed samples; minimum 90% span"


@dataclass(frozen=True)
class FixedWindow:
    points: tuple[GpsPoint, ...]
    start_at: datetime
    end_at: datetime
    observed_span_seconds: float
    complete: bool


def window_at(
    points: Sequence[GpsPoint],
    *,
    end_at: datetime,
    window_seconds: int = WINDOW_SECONDS,
) -> FixedWindow:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    start_at = end_at - timedelta(seconds=window_seconds)
    selected = tuple(point for point in points if start_at <= point.timestamp <= end_at)
    span = (
        (selected[-1].timestamp - selected[0].timestamp).total_seconds()
        if len(selected) >= 2
        else 0.0
    )
    complete = span >= window_seconds * WINDOW_MINIMUM_COVERAGE_RATIO
    return FixedWindow(
        points=selected,
        start_at=start_at,
        end_at=end_at,
        observed_span_seconds=span,
        complete=complete,
    )


def latest_window(
    points: Sequence[GpsPoint],
    *,
    window_seconds: int = WINDOW_SECONDS,
) -> FixedWindow:
    if not points:
        empty_time = datetime.min.replace(tzinfo=UTC)
        return FixedWindow(
            points=(),
            start_at=empty_time,
            end_at=empty_time,
            observed_span_seconds=0.0,
            complete=False,
        )
    return window_at(
        points,
        end_at=points[-1].timestamp,
        window_seconds=window_seconds,
    )


def sliding_windows(
    points: Sequence[GpsPoint],
    *,
    window_seconds: int,
    step_seconds: int = WINDOW_STEP_SECONDS,
) -> Iterator[FixedWindow]:
    if not points:
        return
    if step_seconds <= 0:
        raise ValueError("step_seconds must be positive")
    next_end_at = points[0].timestamp + timedelta(seconds=window_seconds)
    for point in points:
        if point.timestamp < next_end_at:
            continue
        candidate = window_at(
            points,
            end_at=point.timestamp,
            window_seconds=window_seconds,
        )
        if candidate.complete:
            yield candidate
        next_end_at = point.timestamp + timedelta(seconds=step_seconds)
