"""Product-level temporal aggregation of already-scored window states."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class TemporalPolicy(StrEnum):
    SINGLE_WINDOW = "A_single_window"
    TWO_CONSECUTIVE = "B_two_consecutive"
    TWO_OF_THREE = "C_two_of_latest_three"
    THREE_OF_FIVE = "D_three_of_latest_five"


POLICY_REQUIREMENTS: dict[TemporalPolicy, tuple[int, int]] = {
    TemporalPolicy.SINGLE_WINDOW: (1, 1),
    TemporalPolicy.TWO_CONSECUTIVE: (2, 2),
    TemporalPolicy.TWO_OF_THREE: (3, 2),
    TemporalPolicy.THREE_OF_FIVE: (5, 3),
}
SELECTED_TEMPORAL_POLICY = TemporalPolicy.TWO_OF_THREE


def apply_temporal_policy(
    window_alerts: Sequence[bool | None],
    policy: TemporalPolicy,
) -> tuple[bool | None, ...]:
    """Aggregate chronologically ordered window states without changing their scores.

    ``None`` means the current window was UNKNOWN or there was not yet enough
    history for this rule. An UNKNOWN window breaks consecutive evidence and
    counts as non-anomalous in the fixed-size voting rules.
    """
    width, minimum_alerts = POLICY_REQUIREMENTS[policy]
    decisions: list[bool | None] = []
    for index, current in enumerate(window_alerts):
        if current is None or index + 1 < width:
            decisions.append(None)
            continue
        recent = window_alerts[index - width + 1 : index + 1]
        if policy == TemporalPolicy.TWO_CONSECUTIVE:
            decisions.append(all(value is True for value in recent))
        else:
            decisions.append(sum(value is True for value in recent) >= minimum_alerts)
    return tuple(decisions)


def alert_episode_count(decisions: Sequence[bool | None]) -> int:
    """Count product alert episodes as false/unknown -> ATTENTION transitions."""
    return sum(
        decision is True and (index == 0 or decisions[index - 1] is not True)
        for index, decision in enumerate(decisions)
    )
