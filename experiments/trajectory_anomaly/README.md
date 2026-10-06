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

## Temporal product policy (V3)

The Isolation Forest still scores each 10-minute window independently with the unchanged V2 artifact and threshold. The product service converts the last three `NORMAL`/`ATTENTION`/`UNKNOWN` window states into one response using **C: at least two anomalous windows in the latest three**. This temporal decision is a separate service-layer operation; it is not an ML feature. `trajectory_attention.score` remains the raw score for the latest window. Until three complete window states are available, the product status is `UNKNOWN / TEMPORAL_HISTORY_INSUFFICIENT`. A currently unknown window remains `UNKNOWN`; an earlier unknown breaks consecutive evidence and counts as non-anomalous for voting.

The candidates and tie-break protocol were recorded in `results/temporal_policy_protocol.json` before scoring validation/development data. “Clearly lower” was operationalized as at least a 5 percentage-point paired reduction in validation-normal trajectory alert rate and one-sided exact McNemar `p < 0.05` against A. Detection was the unweighted mean of the four behavioral scenario trajectory rates; ties used pooled median delay from event-evidence availability, then rule simplicity. Test normal and the independent stress holdout were excluded until C was frozen.

| Policy | Validation window FPR | Validation normal trajectories alerted | Alerts/trajectory | Development behavioral detection macro | Median delay from evidence |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: any single window | 5.51% | 20/100 (20%) | 0.34 | 100.0% | 604.7 s |
| B: 2 consecutive | 5.51% | 15/100 (15%) | 0.19 | 99.0% | 671.4 s |
| C: at least 2 of latest 3 | 5.51% | 15/100 (15%) | 0.20 | 99.5% | 736.0 s |
| D: at least 3 of latest 5 | 5.51% | 13/100 (13%) | 0.14 | 99.5% | 867.2 s |

B and C each reduced validation trajectory alerts by 5 points (`p = 0.03125`); D reduced them by 7 points (`p = 0.0078125`). C and D tied on behavioral detection; C had the shorter median delay and was frozen. Their validation scenario detection was: long-stop 100%, backtracking 100%, circular 98%, abnormal-speed 100%. Full selection metrics and the artifact hash are in `results/temporal_policy_selection.json`.

The one final holdout pass compared V2 single-window aggregation with frozen V3 C using the same V2 scores:

| Metric | V2 single-window | V3 temporal C |
| --- | ---: | ---: |
| Test-normal window FPR | 5.36% | 5.36% |
| Test-normal trajectories with any ATTENTION | 14/100 (14%) | 12/100 (12%) |
| Test-normal alert episodes per trajectory | 0.21 | 0.13 |
| Long-stop event-aware trajectory detection | 50/50 (100%) | 50/50 (100%) |
| Backtracking event-aware trajectory detection | 50/50 (100%) | 50/50 (100%) |
| Circular event-aware trajectory detection | 47/50 (94%) | 47/50 (94%) |
| Abnormal-speed event-aware trajectory detection | 50/50 (100%) | 50/50 (100%) |
| Pooled median detection delay from evidence | 604.8 s | 735.2 s |

On this holdout, trajectory alert rate fell by 2 points and alert episodes by about 38%; pooled median detection delay increased by about 130 seconds. The final run is saved at `results/temporal_policy_frozen_test.json`. Its evaluator refuses to run again once that file exists. These synthetic results do not establish real-world alert quality.
