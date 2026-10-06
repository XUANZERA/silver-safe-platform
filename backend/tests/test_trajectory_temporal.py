import json
from pathlib import Path

from app.services.trajectory_temporal import (
    SELECTED_TEMPORAL_POLICY,
    TemporalPolicy,
    alert_episode_count,
    apply_temporal_policy,
)


def test_single_window_policy_preserves_current_window_state() -> None:
    assert apply_temporal_policy(
        [True, False, None, True],
        TemporalPolicy.SINGLE_WINDOW,
    ) == (True, False, None, True)


def test_two_consecutive_requires_adjacent_anomalous_windows() -> None:
    assert apply_temporal_policy(
        [True, True, False, True, None, True, True],
        TemporalPolicy.TWO_CONSECUTIVE,
    ) == (None, True, False, False, None, False, True)


def test_two_of_latest_three_counts_unknown_as_not_anomalous() -> None:
    assert apply_temporal_policy(
        [True, False, True, None, True],
        TemporalPolicy.TWO_OF_THREE,
    ) == (None, None, True, None, True)


def test_three_of_latest_five_uses_only_latest_five_states() -> None:
    assert apply_temporal_policy(
        [True, True, None, True, True, False],
        TemporalPolicy.THREE_OF_FIVE,
    ) == (None, None, None, None, True, True)


def test_unknown_decision_breaks_alert_episode() -> None:
    assert alert_episode_count(
        [None, True, True, False, True, None, True, False]
    ) == 3


def test_runtime_policy_matches_frozen_validation_selection() -> None:
    selection_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "trajectory_anomaly"
        / "results"
        / "temporal_policy_selection.json"
    )
    frozen = json.loads(selection_path.read_text(encoding="utf-8"))

    assert frozen["frozen"] is True
    assert frozen["selected_rule"] == SELECTED_TEMPORAL_POLICY.value
