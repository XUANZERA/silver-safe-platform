from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.coordinates import CoordinateReferenceSystem
from app.db.session import SessionLocal
from app.ml.trajectory_anomaly.model import TrajectoryModelError
from app.models.location import Location
from app.models.trip import Trip
from app.services import trajectory_anomaly as trajectory_service
from tests.test_auth import API
from tests.test_locations_and_risk import headers, start_trip


def test_safety_view_exposes_anomaly_separately_from_geofence_risk(
    client: TestClient,
) -> None:
    _, trip_id, elder_id = start_trip(client, with_geofence=True)
    start = datetime.now(UTC) - timedelta(seconds=48 * 15)
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)
        trip.started_at = start
        for index in range(49):
            north_meters = 0.0 if index % 2 == 0 else 100.0
            session.add(
                Location(
                    trip_id=trip_id,
                    client_location_id=f"trajectory-smoke-{index}",
                    latitude=23.1291 + north_meters / 111_195.0,
                    longitude=113.2644,
                    speed_mps=6.67,
                    accuracy_meters=8.0,
                    source="simulation",
                    source_crs=CoordinateReferenceSystem.WGS84.value,
                    recorded_at=start + timedelta(seconds=index * 15),
                )
            )
        session.commit()

    response = client.get(
        f"{API}/elders/{elder_id}/safety",
        headers=headers(client, "family01"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_status"] == "SAFE"
    attention = data["trajectory_attention"]
    assert attention["status"] == "ATTENTION"
    assert attention["score"] is not None
    assert attention["model_version"] == "v2"
    assert "HIGH_TORTUOSITY" in attention["reason_codes"]
    assert "REPEATED_TURNS" in attention["reason_codes"]


def test_safety_view_without_active_trip_reports_unknown_attention(client: TestClient) -> None:
    elders = client.get(f"{API}/elders", headers=headers(client, "family01"))
    elder_id = elders.json()["data"]["items"][0]["id"]

    response = client.get(
        f"{API}/elders/{elder_id}/safety",
        headers=headers(client, "family01"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_status"] is None
    assert data["trajectory_attention"]["status"] == "UNKNOWN"
    assert data["trajectory_attention"]["reason_codes"] == ["NO_ACTIVE_TRIP"]


def test_model_failure_keeps_safety_response_and_risk_status(client, monkeypatch) -> None:
    _, trip_id, elder_id = start_trip(client, with_geofence=True)
    start = datetime.now(UTC) - timedelta(seconds=48 * 15)
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)
        trip.started_at = start
        for index in range(49):
            session.add(
                Location(
                    trip_id=trip_id,
                    client_location_id=f"trajectory-model-failure-{index}",
                    latitude=23.1291 + (index % 2) * 0.0009,
                    longitude=113.2644,
                    speed_mps=6.67,
                    accuracy_meters=8.0,
                    source="simulation",
                    source_crs=CoordinateReferenceSystem.WGS84.value,
                    recorded_at=start + timedelta(seconds=index * 15),
                )
            )
        session.commit()

    def fail_model_load():
        raise TrajectoryModelError("simulated model load failure")

    monkeypatch.setattr(trajectory_service, "_cached_model_bundle", fail_model_load)
    response = client.get(
        f"{API}/elders/{elder_id}/safety",
        headers=headers(client, "family01"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_status"] == "SAFE"
    assert data["trip_status"] == "active"
    assert data["open_alert_count"] == 0
    assert data["trajectory_attention"]["status"] == "UNKNOWN"
    assert data["trajectory_attention"]["reason_codes"] == ["MODEL_UNAVAILABLE"]
