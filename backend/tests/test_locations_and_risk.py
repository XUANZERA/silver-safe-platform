from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.alert import Alert
from app.models.location import Location
from app.models.security import AuditLog
from app.models.trip import Trip
from app.schemas.location import LocationCreateRequest
from app.services.locations import record_location
from tests.test_auth import API, login


def headers(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def start_trip(client: TestClient) -> tuple[dict[str, str], int, int]:
    elder_headers = headers(client, "elder01")
    created = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    ).json()["data"]
    started = client.post(
        f"{API}/trips/{created['id']}/start",
        headers=elder_headers,
    )
    assert started.status_code == 200
    return elder_headers, created["id"], created["elder_id"]


def upload(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    trip_id: int,
    client_location_id: str,
    latitude: float,
    longitude: float,
    recorded_at: datetime,
    accuracy_meters: float | None = 8,
    source: str = "simulation",
):
    return client.post(
        f"{API}/trips/{trip_id}/locations",
        headers=auth_headers,
        json={
            "client_location_id": client_location_id,
            "latitude": latitude,
            "longitude": longitude,
            "speed_mps": 1.2,
            "accuracy_meters": accuracy_meters,
            "source": source,
            "recorded_at": recorded_at.isoformat(),
        },
    )


def test_frontend_simulator_contract_latest_track_and_idempotency(
    client: TestClient,
) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    family_headers = headers(client, "family01")
    start = datetime.now(UTC)

    first = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="sim-001",
        latitude=23.1286,
        longitude=113.2633,
        recorded_at=start,
    )
    second = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="sim-002",
        latitude=23.1288,
        longitude=113.2638,
        recorded_at=start + timedelta(seconds=3),
    )
    repeated = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="sim-002",
        latitude=23.1288,
        longitude=113.2638,
        recorded_at=start + timedelta(seconds=3),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["data"]["id"] == second.json()["data"]["id"]
    assert repeated.json()["data"]["created"] is False
    assert second.json()["data"]["recorded_at"].endswith("Z")

    latest = client.get(
        f"{API}/trips/{trip_id}/locations/latest",
        headers=family_headers,
    )
    track = client.get(
        f"{API}/trips/{trip_id}/locations?limit=1",
        headers=family_headers,
    )
    assert latest.json()["data"]["location"]["id"] == second.json()["data"]["id"]
    assert track.json()["data"]["items"][0]["id"] == second.json()["data"]["id"]
    assert track.json()["data"]["has_more"] is True
    assert "no-store" in latest.headers["cache-control"]
    assert "no-store" in track.headers["cache-control"]


def test_location_validation_permissions_and_conflicting_id(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    family_headers = headers(client, "family01")
    now = datetime.now(UTC)

    invalid = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="invalid",
        latitude=100,
        longitude=113.26,
        recorded_at=now,
    )
    forbidden = upload(
        client,
        family_headers,
        trip_id=trip_id,
        client_location_id="family-forged",
        latitude=23.12,
        longitude=113.26,
        recorded_at=now,
    )
    original = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="same-id",
        latitude=23.12,
        longitude=113.26,
        recorded_at=now,
    )
    conflict = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="same-id",
        latitude=23.13,
        longitude=113.27,
        recorded_at=now,
    )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_COORDINATES"
    assert forbidden.status_code == 403
    assert original.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "LOCATION_ID_CONFLICT"


def test_three_reliable_outside_points_generate_one_event(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    start = datetime.now(UTC)
    points = (
        (23.1295, 113.2677),
        (23.1297, 113.2682),
        (23.1299, 113.2688),
        (23.1300, 113.2690),
    )
    responses = [
        upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"outside-{index}",
            latitude=latitude,
            longitude=longitude,
            recorded_at=start + timedelta(seconds=index * 3),
        )
        for index, (latitude, longitude) in enumerate(points)
    ]

    assert responses[0].json()["data"]["events_created"] == []
    assert responses[1].json()["data"]["events_created"] == []
    assert responses[2].json()["data"]["events_created"][0]["type"] == "geofence_exit"
    assert responses[3].json()["data"]["events_created"] == []
    with SessionLocal() as session:
        assert len(list(session.scalars(select(Alert)))) == 1


def test_inaccurate_and_out_of_order_points_do_not_trigger_event(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    start = datetime.now(UTC)
    for index in range(2):
        upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"new-{index}",
            latitude=23.1299,
            longitude=113.2688,
            recorded_at=start + timedelta(seconds=10 + index),
        )
    inaccurate = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="inaccurate",
        latitude=23.1299,
        longitude=113.2688,
        recorded_at=start + timedelta(seconds=12),
        accuracy_meters=500,
    )
    old = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="old",
        latitude=23.1299,
        longitude=113.2688,
        recorded_at=start + timedelta(seconds=5),
    )

    assert inaccurate.json()["data"]["events_created"] == []
    assert old.json()["data"]["events_created"] == []
    with SessionLocal() as session:
        assert len(list(session.scalars(select(Alert)))) == 0


def test_upload_rate_limit_and_production_simulation_guard(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    settings = get_settings()
    original_limit = settings.location_upload_per_trip
    original_env = settings.app_env
    try:
        settings.location_upload_per_trip = 1
        first = upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id="rate-1",
            latitude=23.1286,
            longitude=113.2633,
            recorded_at=datetime.now(UTC),
        )
        blocked = upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id="rate-2",
            latitude=23.1287,
            longitude=113.2634,
            recorded_at=datetime.now(UTC),
        )
        assert first.status_code == 201
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "LOCATION_RATE_LIMITED"
        assert blocked.headers["retry-after"] == str(settings.location_upload_window_seconds)

        settings.app_env = "production"
        rejected = upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id="prod-sim",
            latitude=23.1287,
            longitude=113.2634,
            recorded_at=datetime.now(UTC),
        )
        assert rejected.status_code == 403
        assert rejected.json()["error"]["code"] == "SIMULATION_NOT_ALLOWED"
    finally:
        settings.location_upload_per_trip = original_limit
        settings.app_env = original_env


def test_location_reads_are_audited_without_polling_log_spam(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    family_headers = headers(client, "family01")
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="audit-1",
        latitude=23.1286,
        longitude=113.2633,
        recorded_at=datetime.now(UTC),
    )
    for _ in range(3):
        response = client.get(
            f"{API}/trips/{trip_id}/locations/latest",
            headers=family_headers,
        )
        assert response.status_code == 200

    with SessionLocal() as session:
        logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "location.latest.read",
                    AuditLog.actor_user_id.is_not(None),
                    AuditLog.resource_id == str(trip_id),
                )
            )
        )
    assert len(logs) == 1


def test_location_queries_have_required_composite_indexes() -> None:
    indexes = {item["name"] for item in inspect(engine).get_indexes("locations")}
    assert "ix_locations_trip_recorded" in indexes
    assert "ix_locations_trip_received" in indexes

    with engine.connect() as connection:
        rate_limit_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM locations "
                "WHERE trip_id = 1 AND received_at >= '2026-01-01' "
                "ORDER BY received_at DESC LIMIT 1 OFFSET 119"
            )
        ).all()
    plan_text = " ".join(str(column) for row in rate_limit_plan for column in row)
    assert "ix_locations_trip_received" in plan_text


def test_concurrent_idempotent_retries_create_one_location(client: TestClient) -> None:
    _, trip_id, _ = start_trip(client)
    recorded_at = datetime.now(UTC)
    barrier = Barrier(2)

    def save() -> tuple[int, bool]:
        with SessionLocal() as session:
            trip = session.get(Trip, trip_id)
            assert trip is not None
            payload = LocationCreateRequest(
                client_location_id="concurrent-retry",
                latitude=23.1286,
                longitude=113.2633,
                speed_mps=1.2,
                accuracy_meters=8,
                source="simulation",
                recorded_at=recorded_at,
            )
            barrier.wait()
            location, _, created = record_location(session, trip=trip, payload=payload)
            return location.id, created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: save(), range(2)))

    assert {location_id for location_id, _ in results} == {results[0][0]}
    assert sorted(created for _, created in results) == [False, True]
    with SessionLocal() as session:
        locations = list(
            session.scalars(
                select(Location).where(Location.client_location_id == "concurrent-retry")
            )
        )
    assert len(locations) == 1
