"""Transparent local-metre GPS simulator; features are never generated directly."""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import cos, degrees, pi, radians, sin
from pathlib import Path

from app.ml.trajectory_anomaly.features import EARTH_RADIUS_METERS, GpsPoint

GENERATOR_VERSION = "v1"
REFERENCE_LATITUDE = 23.1189
REFERENCE_LONGITUDE = 113.2351
SIMULATION_START = datetime(2025, 1, 15, 8, 0, tzinfo=UTC)
DEFAULT_NORMAL_TRIPS_PER_SCENARIO = 100
DEFAULT_STRESS_TRIPS_PER_SCENARIO = 100
DEFAULT_DATASET_SEED = 42

NORMAL_SCENARIOS = (
    "normal_walk",
    "slow_walk",
    "walk_with_short_stop",
    "park_walk",
    "shopping_walk",
)
ANOMALY_SCENARIOS = (
    "long_stop",
    "repeated_backtracking",
    "circular_wandering",
    "abnormal_speed_pattern",
    "gps_jump",
    "gps_dropout",
    "poor_accuracy",
    "severe_timestamp_gap",
)

# All first-version synthetic assumptions live here. These are not real elder statistics.
NORMAL_CONFIG = {
    "duration_seconds": (1500, 1800),
    "sampling_interval_seconds": (5.0, 20.0, 10.0),
    "initial_position_extent_meters": 500.0,
    "walking_speed_mps": {
        "normal_walk": (0.9, 1.6),
        "slow_walk": (0.4, 0.8),
        "walk_with_short_stop": (0.7, 1.4),
        "park_walk": (0.7, 1.35),
        "shopping_walk": (0.45, 1.2),
    },
    "speed_change_sigma_mps": 0.12,
    "speed_smoothing": 0.65,
    "turn_angle_degrees": {
        "normal_walk": (-65.0, 65.0),
        "slow_walk": (-60.0, 60.0),
        "walk_with_short_stop": (-80.0, 80.0),
        "park_walk": (-45.0, 45.0),
        "shopping_walk": (-110.0, 110.0),
    },
    "waypoint_length_meters": {
        "normal_walk": (100.0, 300.0),
        "slow_walk": (90.0, 240.0),
        "walk_with_short_stop": (80.0, 260.0),
        "park_walk": (45.0, 130.0),
        "shopping_walk": (25.0, 110.0),
    },
    "short_stop_count": (1, 5),
    "short_stop_duration_seconds": (10, 60),
    "shopping_stop_count": (4, 10),
    "shopping_stop_duration_seconds": (20, 150),
    "park_turns_per_minute": (0.5, 2.0),
    "park_turn_angle_sigma_degrees": 25.0,
    "short_stop_time_fraction": (0.12, 0.88),
    "shopping_stop_initial_seconds": (50, 150),
    "shopping_stop_spacing_seconds": (120, 260),
    "gps_noise_sigma_meters": (1.5, 3.5),
    "reported_accuracy_meters": (3.0, 18.0),
    "reported_accuracy_noise_sigma_meters": 2.0,
    "reported_accuracy_sigma_multiplier": 2.0,
}

ANOMALY_CONFIG = {
    "long_stop_seconds": (480, 900),
    "backtracking_leg_meters": (90.0, 190.0),
    "backtracking_speed_mps": (0.6, 1.35),
    "circle_radius_meters": (45.0, 130.0),
    "circle_walking_speed_mps": (0.65, 1.45),
    "circle_path_wobble_sigma_meters": 3.0,
    "circle_radial_noise_sigma_meters": 2.0,
    "long_stop_time_fraction": (0.25, 0.65),
    "abnormal_slow_speed_mps": (0.15, 0.35),
    "abnormal_burst_speed_mps": (3.5, 5.5),
    "abnormal_speed_phase_seconds": (20, 100),
    "abnormal_speed_switch_threshold_mps": 1.0,
    "gps_jump_offset_meters": (40.0, 110.0),
    "gps_jump_index_margins": (5, 6),
    "gps_dropout_seconds": (180, 300),
    "gps_dropout_start_min_index": 8,
    "gps_dropout_start_fraction": 0.33,
    "poor_accuracy_meters": (80.0, 250.0),
    "severe_timestamp_gap_seconds": (240, 600),
    "severe_gap_index_margins": (8, 12),
    "scenario_seed_stride": 1_000_003,
    "trip_seed_stride": 97,
}


@dataclass(frozen=True)
class SimulatedTrip:
    trajectory_id: str
    scenario: str
    is_synthetic: bool
    points: tuple[GpsPoint, ...]
    behavior_start_seconds: float | None = None

    def raw_rows(self) -> Iterable[dict[str, object]]:
        for point in self.points:
            yield {
                "trajectory_id": self.trajectory_id,
                "scenario": self.scenario,
                "is_synthetic": self.is_synthetic,
                "timestamp": point.timestamp.isoformat(),
                "latitude": point.latitude,
                "longitude": point.longitude,
                "accuracy": point.accuracy_meters,
            }


def local_xy_to_wgs84(x_meters: float, y_meters: float) -> tuple[float, float]:
    """Convert local east/north metres around one reference point to WGS84."""
    latitude = REFERENCE_LATITUDE + degrees(y_meters / EARTH_RADIUS_METERS)
    longitude = REFERENCE_LONGITUDE + degrees(
        x_meters / (EARTH_RADIUS_METERS * cos(radians(REFERENCE_LATITUDE)))
    )
    return latitude, longitude


def _sampling_interval(rng: random.Random) -> float:
    low, high, mode = NORMAL_CONFIG["sampling_interval_seconds"]
    return rng.triangular(low, high, mode)


def _sample_route(
    scenario: str,
    rng: random.Random,
) -> tuple[list[tuple[float, float, float]], float, float | None]:
    """Return true local x/y and elapsed-seconds samples before GPS measurement noise."""
    route_scenario = scenario if scenario in NORMAL_SCENARIOS else "normal_walk"
    duration = float(rng.randint(*NORMAL_CONFIG["duration_seconds"]))
    start_extent = NORMAL_CONFIG["initial_position_extent_meters"]
    start_x, start_y = (
        rng.uniform(-start_extent, start_extent),
        rng.uniform(-start_extent, start_extent),
    )
    x, y = start_x, start_y
    heading = rng.uniform(-pi, pi)
    base_speed = rng.uniform(*NORMAL_CONFIG["walking_speed_mps"][route_scenario])
    current_speed = base_speed
    if route_scenario == "park_walk":
        turns_per_minute = rng.uniform(*NORMAL_CONFIG["park_turns_per_minute"])
        waypoint_distance = base_speed * 60.0 / turns_per_minute
    else:
        waypoint_distance = rng.uniform(*NORMAL_CONFIG["waypoint_length_meters"][route_scenario])
    distance_on_leg = 0.0
    points = [(x, y, 0.0)]

    stop_windows: list[tuple[float, float]] = []
    if scenario == "walk_with_short_stop":
        for _ in range(rng.randint(*NORMAL_CONFIG["short_stop_count"])):
            stop_windows.append(
                (
                    rng.uniform(
                        duration * NORMAL_CONFIG["short_stop_time_fraction"][0],
                        duration * NORMAL_CONFIG["short_stop_time_fraction"][1],
                    ),
                    rng.randint(*NORMAL_CONFIG["short_stop_duration_seconds"]),
                )
            )
    elif scenario == "shopping_walk":
        cursor = rng.uniform(*NORMAL_CONFIG["shopping_stop_initial_seconds"])
        for _ in range(rng.randint(*NORMAL_CONFIG["shopping_stop_count"])):
            stop_windows.append(
                (cursor, rng.randint(*NORMAL_CONFIG["shopping_stop_duration_seconds"]))
            )
            cursor += rng.uniform(*NORMAL_CONFIG["shopping_stop_spacing_seconds"])

    long_stop = None
    behavior_start_seconds = None
    if scenario == "long_stop":
        stop_duration = rng.randint(*ANOMALY_CONFIG["long_stop_seconds"])
        stop_start = rng.uniform(
            duration * ANOMALY_CONFIG["long_stop_time_fraction"][0],
            duration * ANOMALY_CONFIG["long_stop_time_fraction"][1],
        )
        long_stop = (stop_start, stop_duration)
        behavior_start_seconds = stop_start

    elapsed = 0.0
    phase_remaining = 0.0
    circular_angle = rng.uniform(-pi, pi)
    circular_radius = rng.uniform(*ANOMALY_CONFIG["circle_radius_meters"])
    circular_center = (x, y)
    circle_direction = rng.choice((-1.0, 1.0))
    while elapsed < duration:
        remaining = duration - elapsed
        if remaining < NORMAL_CONFIG["sampling_interval_seconds"][0]:
            break
        interval = min(_sampling_interval(rng), remaining)
        next_elapsed = elapsed + interval
        stopped = any(start <= elapsed < start + length for start, length in stop_windows)
        if long_stop is not None:
            stopped = stopped or long_stop[0] <= elapsed < long_stop[0] + long_stop[1]

        if scenario == "circular_wandering":
            current_speed = rng.uniform(*ANOMALY_CONFIG["circle_walking_speed_mps"])
            circular_angle += circle_direction * current_speed * interval / circular_radius
            wobble = rng.gauss(0.0, ANOMALY_CONFIG["circle_path_wobble_sigma_meters"])
            x = circular_center[0] + (circular_radius + wobble) * cos(circular_angle)
            y = circular_center[1] + (circular_radius + wobble) * sin(circular_angle)
        elif not stopped:
            if scenario == "repeated_backtracking":
                leg_index = int(distance_on_leg // waypoint_distance)
                heading = (heading if leg_index % 2 == 0 else heading + pi) % (2 * pi)
                current_speed = rng.uniform(*ANOMALY_CONFIG["backtracking_speed_mps"])
                step_distance = current_speed * interval
                x += sin(heading) * step_distance
                y += cos(heading) * step_distance
                distance_on_leg += step_distance
                waypoint_distance = (
                    waypoint_distance
                    if distance_on_leg < waypoint_distance
                    else rng.uniform(*ANOMALY_CONFIG["backtracking_leg_meters"])
                )
                if distance_on_leg >= waypoint_distance:
                    distance_on_leg = 0.0
                    heading = (heading + pi) % (2 * pi)
            else:
                target_speed = base_speed
                if scenario == "abnormal_speed_pattern":
                    if phase_remaining <= 0:
                        current_speed = rng.uniform(
                            *(
                                ANOMALY_CONFIG["abnormal_slow_speed_mps"]
                                if current_speed
                                > ANOMALY_CONFIG["abnormal_speed_switch_threshold_mps"]
                                else ANOMALY_CONFIG["abnormal_burst_speed_mps"]
                            )
                        )
                        phase_remaining = rng.randint(
                            *ANOMALY_CONFIG["abnormal_speed_phase_seconds"]
                        )
                    target_speed = current_speed
                    phase_remaining -= interval
                current_speed = (
                    NORMAL_CONFIG["speed_smoothing"] * current_speed
                    + (1 - NORMAL_CONFIG["speed_smoothing"]) * target_speed
                    + rng.gauss(0.0, NORMAL_CONFIG["speed_change_sigma_mps"])
                )
                current_speed = max(0.1, current_speed)

                distance_left = waypoint_distance - distance_on_leg
                step_distance = min(current_speed * interval, max(0.0, distance_left))
                x += sin(heading) * step_distance
                y += cos(heading) * step_distance
                distance_on_leg += step_distance
                if distance_on_leg >= waypoint_distance - 1e-6:
                    turn_low, turn_high = NORMAL_CONFIG["turn_angle_degrees"][route_scenario]
                    if route_scenario == "park_walk":
                        turn = rng.gauss(
                            0.0,
                            NORMAL_CONFIG["park_turn_angle_sigma_degrees"],
                        )
                    else:
                        turn = rng.uniform(turn_low, turn_high)
                    heading = (heading + radians(turn)) % (2 * pi)
                    distance_on_leg = 0.0
                    if route_scenario == "park_walk":
                        turns_per_minute = rng.uniform(*NORMAL_CONFIG["park_turns_per_minute"])
                        waypoint_distance = current_speed * 60.0 / turns_per_minute
                    else:
                        waypoint_distance = rng.uniform(
                            *NORMAL_CONFIG["waypoint_length_meters"][route_scenario]
                        )
                if scenario == "abnormal_speed_pattern":
                    # Movement bursts are intentionally outside the normal speed range.
                    current_speed = target_speed

        elapsed = next_elapsed
        points.append((x, y, elapsed))

    return points, duration, behavior_start_seconds


def generate_trip(scenario: str, *, seed: int, trajectory_id: str) -> SimulatedTrip:
    if scenario not in NORMAL_SCENARIOS + ANOMALY_SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    rng = random.Random(seed)
    local_points, _, behavior_start_seconds = _sample_route(scenario, rng)

    if scenario in (
        "repeated_backtracking",
        "circular_wandering",
        "abnormal_speed_pattern",
    ):
        behavior_start_seconds = 0.0

    # Replace movement for explicit behavioral anomaly scenarios where needed.
    if scenario == "repeated_backtracking":
        duration = local_points[-1][2]
        x, y = local_points[0][0], local_points[0][1]
        heading = rng.uniform(-pi, pi)
        speed = rng.uniform(*ANOMALY_CONFIG["backtracking_speed_mps"])
        leg_length = rng.uniform(*ANOMALY_CONFIG["backtracking_leg_meters"])
        walked = 0.0
        local_points = [(x, y, 0.0)]
        for _, _, timestamp in _time_grid(duration, rng):
            interval = timestamp - local_points[-1][2]
            step = speed * interval
            if walked + step >= leg_length:
                step = leg_length - walked
            x += sin(heading) * step
            y += cos(heading) * step
            walked += step
            if walked >= leg_length:
                heading = (heading + pi) % (2 * pi)
                walked = 0.0
                leg_length = rng.uniform(*ANOMALY_CONFIG["backtracking_leg_meters"])
            local_points.append((x, y, timestamp))
    elif scenario == "circular_wandering":
        duration = local_points[-1][2]
        center_x, center_y = local_points[0][0], local_points[0][1]
        radius = rng.uniform(*ANOMALY_CONFIG["circle_radius_meters"])
        angle = rng.uniform(-pi, pi)
        direction = rng.choice((-1.0, 1.0))
        local_points = [(center_x + radius * cos(angle), center_y + radius * sin(angle), 0.0)]
        for _, _, timestamp in _time_grid(duration, rng):
            interval = timestamp - local_points[-1][2]
            speed = rng.uniform(*ANOMALY_CONFIG["circle_walking_speed_mps"])
            angle += direction * speed * interval / radius
            radial_noise = rng.gauss(
                0.0,
                ANOMALY_CONFIG["circle_radial_noise_sigma_meters"],
            )
            local_points.append(
                (
                    center_x + (radius + radial_noise) * cos(angle),
                    center_y + (radius + radial_noise) * sin(angle),
                    timestamp,
                )
            )

    noise_sigma = rng.uniform(*NORMAL_CONFIG["gps_noise_sigma_meters"])
    points: list[GpsPoint] = []
    for x, y, elapsed in local_points:
        noisy_lat, noisy_lon = local_xy_to_wgs84(
            x + rng.gauss(0.0, noise_sigma),
            y + rng.gauss(0.0, noise_sigma),
        )
        accuracy = min(
            NORMAL_CONFIG["reported_accuracy_meters"][1],
            max(
                NORMAL_CONFIG["reported_accuracy_meters"][0],
                rng.gauss(
                    noise_sigma * NORMAL_CONFIG["reported_accuracy_sigma_multiplier"],
                    NORMAL_CONFIG["reported_accuracy_noise_sigma_meters"],
                ),
            ),
        )
        points.append(
            GpsPoint(
                timestamp=SIMULATION_START + timedelta(seconds=elapsed),
                latitude=noisy_lat,
                longitude=noisy_lon,
                accuracy_meters=accuracy,
            )
        )

    if scenario == "gps_jump":
        lower_margin, upper_margin = ANOMALY_CONFIG["gps_jump_index_margins"]
        index = rng.randint(lower_margin, len(points) - upper_margin)
        offset = rng.uniform(*ANOMALY_CONFIG["gps_jump_offset_meters"])
        jump_bearing = rng.uniform(-pi, pi)
        original = points[index]
        latitude, longitude = local_xy_to_wgs84(
            offset * cos(jump_bearing), offset * sin(jump_bearing)
        )
        points[index] = GpsPoint(
            timestamp=original.timestamp,
            latitude=original.latitude + latitude - REFERENCE_LATITUDE,
            longitude=original.longitude + longitude - REFERENCE_LONGITUDE,
            accuracy_meters=original.accuracy_meters,
        )
    elif scenario == "gps_dropout":
        minimum_start = ANOMALY_CONFIG["gps_dropout_start_min_index"]
        maximum_start = max(
            minimum_start,
            int(len(points) * ANOMALY_CONFIG["gps_dropout_start_fraction"]),
        )
        start = rng.randint(minimum_start, maximum_start)
        end_time = points[start].timestamp + timedelta(
            seconds=rng.randint(*ANOMALY_CONFIG["gps_dropout_seconds"])
        )
        points = [
            point
            for index, point in enumerate(points)
            if index <= start or point.timestamp >= end_time
        ]
    elif scenario == "poor_accuracy":
        points = [
            GpsPoint(
                timestamp=point.timestamp,
                latitude=point.latitude,
                longitude=point.longitude,
                accuracy_meters=rng.uniform(*ANOMALY_CONFIG["poor_accuracy_meters"]),
            )
            for point in points
        ]
    elif scenario == "severe_timestamp_gap":
        lower_margin, upper_margin = ANOMALY_CONFIG["severe_gap_index_margins"]
        index = rng.randint(lower_margin, len(points) - upper_margin)
        gap = timedelta(seconds=rng.randint(*ANOMALY_CONFIG["severe_timestamp_gap_seconds"]))
        points = [
            GpsPoint(
                timestamp=point.timestamp + (gap if position > index else timedelta()),
                latitude=point.latitude,
                longitude=point.longitude,
                accuracy_meters=point.accuracy_meters,
            )
            for position, point in enumerate(points)
        ]
    return SimulatedTrip(
        trajectory_id=trajectory_id,
        scenario=scenario,
        is_synthetic=True,
        points=tuple(points),
        behavior_start_seconds=behavior_start_seconds,
    )


def _time_grid(duration: float, rng: random.Random) -> Iterable[tuple[float, float, float]]:
    elapsed = 0.0
    while elapsed < duration:
        interval = _sampling_interval(rng)
        if duration - elapsed < NORMAL_CONFIG["sampling_interval_seconds"][0]:
            break
        elapsed = min(duration, elapsed + interval)
        yield 0.0, 0.0, elapsed


def generate_dataset(
    *,
    normal_trips_per_scenario: int = DEFAULT_NORMAL_TRIPS_PER_SCENARIO,
    stress_trips_per_scenario: int = DEFAULT_STRESS_TRIPS_PER_SCENARIO,
    seed: int = DEFAULT_DATASET_SEED,
) -> list[SimulatedTrip]:
    """Generate all configured scenarios with one stable ID and seed per trip."""
    trips: list[SimulatedTrip] = []
    scenario_index = 0
    for scenarios, count in (
        (NORMAL_SCENARIOS, normal_trips_per_scenario),
        (ANOMALY_SCENARIOS, stress_trips_per_scenario),
    ):
        for scenario in scenarios:
            for index in range(count):
                trip_seed = (
                    seed
                    + scenario_index * ANOMALY_CONFIG["scenario_seed_stride"]
                    + index * ANOMALY_CONFIG["trip_seed_stride"]
                )
                trip_id = f"{scenario}-{index + 1:03d}"
                trips.append(generate_trip(scenario, seed=trip_seed, trajectory_id=trip_id))
            scenario_index += 1
    return trips


def write_raw_csv(trips: list[SimulatedTrip], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "trajectory_id",
        "scenario",
        "is_synthetic",
        "timestamp",
        "latitude",
        "longitude",
        "accuracy",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for trip in trips:
            writer.writerows(trip.raw_rows())


def main() -> None:
    from experiments.trajectory_anomaly.dataset import RESULTS_DIR

    trips = generate_dataset()
    output_path = RESULTS_DIR / "synthetic_trajectories.csv"
    write_raw_csv(trips, output_path)
    print(
        json.dumps(
            {
                "normal_trips": DEFAULT_NORMAL_TRIPS_PER_SCENARIO * len(NORMAL_SCENARIOS),
                "stress_test_trips": DEFAULT_STRESS_TRIPS_PER_SCENARIO * len(ANOMALY_SCENARIOS),
                "raw_gps_csv": str(output_path),
                "synthetic_generator_version": GENERATOR_VERSION,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
