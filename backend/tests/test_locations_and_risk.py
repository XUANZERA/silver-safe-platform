from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text

import app.services.locations as location_service
from app.core.config import get_settings
from app.core.coordinates import CoordinateReferenceSystem
from app.db.schema_compat import add_legacy_coordinate_columns
from app.db.session import SessionLocal, engine
from app.models.alert import Alert
from app.models.geofence import Geofence
from app.models.location import Location
from app.models.security import AuditLog
from app.models.trip import Trip
from app.schemas.location import LocationCreateRequest
from app.services.locations import record_location
from tests.test_auth import API, login


def headers(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_wgs84_geofence(
    elder_id: int,
    *,
    center_latitude: float = 23.1291,
    center_longitude: float = 113.2644,
    radius_meters: int = 300,
) -> Geofence:
    with SessionLocal() as session:
        geofence = session.scalar(select(Geofence).where(Geofence.elder_id == elder_id))
        if geofence is None:
            geofence = Geofence(
                elder_id=elder_id,
                center_latitude=center_latitude,
                center_longitude=center_longitude,
                radius_meters=radius_meters,
                enabled=True,
                crs=CoordinateReferenceSystem.WGS84.value,
            )
            session.add(geofence)
        else:
            geofence.center_latitude = center_latitude
            geofence.center_longitude = center_longitude
            geofence.radius_meters = radius_meters
            geofence.enabled = True
            geofence.crs = CoordinateReferenceSystem.WGS84.value
        session.commit()
        return geofence


def start_trip(
    client: TestClient,
    *,
    with_geofence: bool = False,
) -> tuple[dict[str, str], int, int]:
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
    if with_geofence:
        setup_wgs84_geofence(created["elder_id"])
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
    source_crs: str = "WGS84",
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
            "source_crs": source_crs,
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
    assert second.json()["data"]["source_crs"] == "WGS84"

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
    assert track.json()["data"]["items"][0]["source_crs"] == "WGS84"
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


def test_location_upload_rejects_inactive_trip_without_persistence(client: TestClient) -> None:
    elder_headers = headers(client, "elder01")
    trip = client.post(
        f"{API}/trips",
        headers=elder_headers,
        json={"destination": "人民公园"},
    ).json()["data"]
    response = upload(
        client,
        elder_headers,
        trip_id=trip["id"],
        client_location_id="inactive-trip",
        latitude=23.1291,
        longitude=113.2644,
        source="h5",
        recorded_at=datetime.now(UTC),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_ACTIVE"
    with SessionLocal() as session:
        assert list(session.scalars(select(Location)).all()) == []


def test_source_crs_is_required_and_only_exact_wgs84_is_accepted(
    client: TestClient,
    monkeypatch,
) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    risk_calls = 0

    def unexpected_risk(*_args, **_kwargs):
        nonlocal risk_calls
        risk_calls += 1
        return []

    monkeypatch.setattr(location_service, "evaluate_location_risk", unexpected_risk)
    base_payload = {
        "client_location_id": "crs-contract",
        "latitude": 23.1291,
        "longitude": 113.2644,
        "speed_mps": None,
        "accuracy_meters": 8,
        "source": "h5",
        "recorded_at": datetime.now(UTC).isoformat(),
    }

    missing = client.post(
        f"{API}/trips/{trip_id}/locations",
        headers=elder_headers,
        json=base_payload,
    )
    assert missing.status_code == 422

    for source_crs in ("GCJ02", "wgs84", "WGS-84", "EPSG:4326", "UNKNOWN"):
        rejected = client.post(
            f"{API}/trips/{trip_id}/locations",
            headers=elder_headers,
            json={**base_payload, "source_crs": source_crs},
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "UNSUPPORTED_SOURCE_CRS"

    with SessionLocal() as session:
        assert list(session.scalars(select(Location)).all()) == []
    assert risk_calls == 0


def test_wgs84_normalization_precedes_persistence_and_risk(
    client: TestClient,
    monkeypatch,
) -> None:
    elder_headers, trip_id, _ = start_trip(client)
    calls: list[str] = []
    original_normalize = location_service.normalize_location_coordinates

    def tracked_normalize(**kwargs):
        calls.append("normalize")
        assert kwargs["source_crs"] == "WGS84"
        return original_normalize(**kwargs)

    def tracked_risk(_db, location):
        calls.append("risk")
        assert location.source_crs == "WGS84"
        assert location.latitude == 23.1291
        assert location.longitude == 113.2644
        return []

    monkeypatch.setattr(location_service, "normalize_location_coordinates", tracked_normalize)
    monkeypatch.setattr(location_service, "evaluate_location_risk", tracked_risk)
    response = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="wgs84-order",
        latitude=23.1291,
        longitude=113.2644,
        source="h5",
        source_crs="WGS84",
        recorded_at=datetime.now(UTC),
    )

    assert response.status_code == 201
    assert calls == ["normalize", "risk"]
    with SessionLocal() as session:
        saved = session.scalar(select(Location).where(Location.client_location_id == "wgs84-order"))
        assert saved is not None
        assert saved.source_crs == "WGS84"
        assert saved.latitude == 23.1291
        assert saved.longitude == 113.2644


def test_three_reliable_outside_points_generate_one_event(client: TestClient) -> None:
    elder_headers, trip_id, _ = start_trip(client, with_geofence=True)
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
    elder_headers, trip_id, _ = start_trip(client, with_geofence=True)
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
    location_checks = {item["name"] for item in inspect(engine).get_check_constraints("locations")}
    geofence_checks = {item["name"] for item in inspect(engine).get_check_constraints("geofences")}
    assert "ck_locations_source_crs" in location_checks
    assert "ck_geofences_crs" in geofence_checks

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


def test_legacy_sqlite_crs_columns_do_not_guess_existing_coordinate_systems() -> None:
    legacy_engine = create_engine("sqlite://")
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE locations (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE geofences (elder_id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO locations (id) VALUES (1)"))
        connection.execute(text("INSERT INTO geofences (elder_id) VALUES (1)"))

    add_legacy_coordinate_columns(legacy_engine)
    legacy_inspector = inspect(legacy_engine)
    assert "source_crs" in {column["name"] for column in legacy_inspector.get_columns("locations")}
    assert "crs" in {column["name"] for column in legacy_inspector.get_columns("geofences")}
    with legacy_engine.connect() as connection:
        assert connection.scalar(text("SELECT source_crs FROM locations WHERE id = 1")) is None
        assert connection.scalar(text("SELECT crs FROM geofences WHERE elder_id = 1")) is None
    legacy_engine.dispose()


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
                source_crs="WGS84",
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


def test_real_wgs84_location_not_misjudged_as_exit_due_to_legacy_gcj02_geofence(
    client: TestClient,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client, with_geofence=False)
    with SessionLocal() as session:
        geofence = session.scalar(select(Geofence).where(Geofence.elder_id == elder_id))
        if geofence is None:
            geofence = Geofence(
                elder_id=elder_id,
                center_latitude=23.1291,
                center_longitude=113.2644,
                radius_meters=300,
                enabled=True,
                crs=None,
            )
            session.add(geofence)
        else:
            geofence.center_latitude = 23.1291
            geofence.center_longitude = 113.2644
            geofence.radius_meters = 300
            geofence.enabled = True
            geofence.crs = None
        session.commit()

    start = datetime.now(UTC)
    for index in range(4):
        response = upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"outside-wgs84-{index}",
            latitude=23.1299,
            longitude=113.2688,
            recorded_at=start + timedelta(seconds=index * 3),
            source="h5",
            source_crs="WGS84",
        )
        assert response.status_code == 201
        assert response.json()["data"]["events_created"] == []

    with SessionLocal() as session:
        assert len(list(session.scalars(select(Alert).where(Alert.trip_id == trip_id)))) == 0
