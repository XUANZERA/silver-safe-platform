# Trajectory anomaly experiment

This is a fixed-window **statistical trajectory anomaly hint**, not a fall, illness, lost-person, danger, or alarm predictor. The public status values are `NORMAL`, `ATTENTION`, and `UNKNOWN`. All generated values are engineering assumptions for pipeline testing, not measured older-adult movement statistics.

## Data flow

The simulator creates timestamped latitude, longitude, and accuracy samples. It simulates east/north metres around one fixed reference coordinate, then converts to WGS84 with a local small-area approximation:

```text
latitude  = latitude0  + (north_m / R) × 180/π
longitude = longitude0 + (east_m / (R × cos(latitude0))) × 180/π
R = 6,371,000 metres
```

The simulator still generates 25?30 minute trajectories with 5?20 second sampling intervals. The model consumes fixed 10-minute elapsed-time windows ending at observed GPS samples; evaluation advances those windows in 60-second steps, while production scores the latest complete window. A window needs at least 90% observed time coverage. The simulator parameters and generated points are unchanged. `NORMAL_CONFIG` and `ANOMALY_CONFIG` contain the simulator's assumptions. Seed `42` produces a repeatable dataset.

Each trajectory is passed through the same quality gate and feature extractor used by application inference. The quality gate returns `UNKNOWN` for fewer than 20 points, less than 300 seconds, any non-increasing timestamps, gaps above 120 seconds, less than 80% accuracy coverage, median accuracy above 40 metres, mean accuracy above 50 metres, or implied speed above 20 m/s. Invalid trajectories are not scored by Isolation Forest.

The ten fixed-order features are:

| Feature | Definition |
| --- | --- |
| `median_speed` | Median of Haversine segment distance divided by positive segment time, m/s |
| `speed_std` | Population standard deviation of segment speeds, m/s |
| `max_speed` | Maximum segment speed, m/s |
| `path_length` | Sum of adjacent Haversine distances, metres |
| `direct_distance` | Haversine distance between the first and last point, metres |
| `tortuosity` | `min(10, path_length / max(direct_distance, 10 m))`; the floor and cap bound near-zero displacement |
| `longest_stop_seconds` | Longest anchor-radius episode with low cluster speed, seconds |
| `stop_ratio` | Accepted low-movement episode seconds / window span, bounded to [0, 1] |
| `large_turn_count` | Wrapped heading changes of at least 100° where both segments are at least `max(8 m, 1.25 × median accuracy)` |
| `mean_accuracy` | Arithmetic mean of available reported accuracy, metres |

Turn differences use `atan2(sin(Δ), cos(Δ))`, so a 359° to 1° change is about 2°, not a 358° reversal. Haversine handles adjacent-point distance; the local equirectangular approximation is used only for headings and synthetic coordinate conversion.

## Evaluation design

The default dataset has 100 trajectories for each of five normal scenarios and 100 for each of eight generated anomaly scenarios. Normal trajectory IDs are split 60/20/20 before window extraction; overlapping windows from one trajectory remain in the same split. Generated anomaly trajectories are split into a development subset and a disjoint final stress-test subset. Window selection uses only normal train/validation and development long-stop/backtracking trajectories. It excludes normal test and final stress-test data.

The 10-minute window was selected against a fixed 15-minute alternative. Both candidates had validation-normal window FPR about 4.96% (target 5%). On development trajectories, 10 minutes gave 100% long-stop sensitivity after at least 300 seconds of event evidence and 100% backtracking sensitivity; 15 minutes gave 90% and 100%. Minimum decision latency is 10 versus 15 minutes. The 10-minute choice is frozen in `windows.py`; candidate results are in `results/window_selection.json`. Any-window validation-normal trajectory FPR was 17% for 10 minutes versus 12% for 15 minutes, exposing a repeated-window false-alert tradeoff.

Five Isolation Forest seeds `42` through `46` use 200 estimators, `max_samples="auto"`, `max_features=1.0`, `contamination="auto"`, and `n_jobs=-1`. Only normal train windows are fit. The score is `-decision_function`, so higher means more abnormal. The threshold is calibrated on held-out normal validation windows only. Development anomalies select the window length but never fit the model or calibrate the threshold; final test/stress data does neither.

The fixed rule baseline is the OR of `LONG_STOP` (300 seconds), `HIGH_TORTUOSITY` (3.5), and `REPEATED_TURNS` (3). It is not calibrated. Rule reason codes are direct feature/rule inspection and are not claimed to be causal explanations produced by Isolation Forest.

The final production model is refit with train-normal plus validation-normal windows and saved with the fixed window definition and finite validation threshold. Test-normal and final stress windows are scored only after selection and training. Metrics are reported per window and, for sensitivity/FPR, per trajectory with at least one alerted window. Overlapping windows are correlated, so these counts are not independent samples. AUROC/AUPRC describe synthetic stress-test discrimination only and do not estimate real-world safety performance.

## Commands

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'backend'
python -m experiments.trajectory_anomaly.simulate
python -m pytest backend/tests/test_trajectory_features.py backend/tests/test_trajectory_quality.py
python -m experiments.trajectory_anomaly.select_window
python -m experiments.trajectory_anomaly.evaluate
python -m experiments.trajectory_anomaly.train
python -m experiments.trajectory_anomaly.smoke_test
python -m pytest backend/tests
```

The backend loads the saved artifact once on first valid scoring request. If it is missing or incompatible, `trajectory_attention.status` is `UNKNOWN` with `MODEL_UNAVAILABLE`; the existing `risk_status` path remains independent.
