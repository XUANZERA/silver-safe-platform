from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.elder import Elder
from app.models.location import Location
from app.models.security import AuditLog
from app.models.trip import Trip
from app.models.user import User
from tests.test_auth import API
from tests.test_locations_and_risk import headers, start_trip, upload


@contextmanager
def stale_threshold(seconds: int | None) -> Iterator[None]:
    settings = get_settings()
    original = settings.location_stale_after_seconds
    try:
        settings.location_stale_after_seconds = seconds
        yield
    finally:
        settings.location_stale_after_seconds = original


def accessible_elder_id(client: TestClient) -> int:
    response = client.get(f"{API}/elders", headers=headers(client, "family01"))
    assert response.status_code == 200
    return response.json()["data"]["items"][0]["id"]


def safety(client: TestClient, elder_id: int, username: str = "family01") -> dict:
    response = client.get(
        f"{API}/elders/{elder_id}/safety",
        headers=headers(client, username),
    )
    assert response.status_code == 200
    return response.json()["data"]


def business_state_snapshot() -> dict[str, list[tuple[object, ...]]]:
    with SessionLocal() as session:
        trips = list(session.scalars(select(Trip).order_by(Trip.id)).all())
        locations = list(session.scalars(select(Location).order_by(Location.id)).all())
        alerts = list(session.scalars(select(Alert).order_by(Alert.id)).all())
        return {
            "trips": [
                (
                    item.id,
                    item.elder_id,
                    item.destination,
                    item.status,
                    item.created_at,
                    item.started_at,
                    item.ended_at,
                    item.cancelled_at,
                    item.cancel_reason,
                )
                for item in trips
            ],
            "locations": [
                (
                    item.id,
                    item.trip_id,
                    item.client_location_id,
                    item.latitude,
                    item.longitude,
                    item.speed_mps,
                    item.accuracy_meters,
                    item.source,
                    item.source_crs,
                    item.recorded_at,
                    item.received_at,
                )
                for item in locations
            ],
            "alerts": [
                (
                    item.id,
                    item.elder_id,
                    item.trip_id,
                    item.type,
                    item.status,
                    item.latitude,
                    item.longitude,
                    item.handler_id,
                    item.resolution,
                    item.occurred_at,
                    item.accepted_at,
                    item.resolved_at,
                )
                for item in alerts
            ],
        }


def test_tc_safety_001_no_active_trip(client: TestClient) -> None:
    data = safety(client, accessible_elder_id(client))

    assert data["trip_status"] is None
    assert data["location_health"] == "NO_DATA"
    assert data["risk_status"] is None
    assert data["open_alert_count"] == 0
    assert data["latest_location"] is None
    assert data["latest_open_alert"] is None


def test_tc_safety_002_active_trip_without_location(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)

    data = safety(client, elder_id)

    assert data["trip_status"] == "active"
    assert data["location_health"] == "NO_DATA"
    assert data["risk_status"] is None


def test_tc_safety_003_active_trip_with_fresh_valid_location(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client, with_geofence=True)
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="inside-fresh",
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=datetime.now(UTC),
    )

    with stale_threshold(300):
        data = safety(client, elder_id)

    assert data["location_health"] == "FRESH"
    assert data["risk_status"] == "SAFE"
    assert data["latest_location"]["client_location_id"] == "inside-fresh"
    assert data["latest_location"]["source_crs"] == "WGS84"
    assert data["latest_location"]["latitude"] == 23.1291
    assert data["latest_location"]["longitude"] == 113.2644


def test_tc_safety_004_backend_risk_pending(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client, with_geofence=True)
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="outside-pending",
        latitude=23.1299,
        longitude=113.2688,
        recorded_at=datetime.now(UTC),
    )

    with stale_threshold(300):
        data = safety(client, elder_id)

    assert data["location_health"] == "FRESH"
    assert data["risk_status"] == "PENDING"
    assert data["open_alert_count"] == 0


def test_tc_safety_005_backend_risk_alert(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client, with_geofence=True)
    start = datetime.now(UTC)
    for index in range(3):
        upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"outside-alert-{index}",
            latitude=23.1299,
            longitude=113.2688,
            recorded_at=start + timedelta(seconds=index),
        )

    with stale_threshold(300):
        data = safety(client, elder_id)

    assert data["risk_status"] == "ALERT"
    assert data["open_alert_count"] == 1
    assert data["latest_open_alert"]["type"] == "geofence_exit"
    assert data["latest_open_alert"]["status"] == "new"


def test_tc_safety_006_safe_risk_with_processing_alert(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client, with_geofence=True)
    start = datetime.now(UTC)
    alert_id = None
    for index in range(3):
        response = upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"outside-processing-{index}",
            latitude=23.1299,
            longitude=113.2688,
            recorded_at=start + timedelta(seconds=index),
        )
        events = response.json()["data"]["events_created"]
        if events:
            alert_id = events[0]["id"]
    assert alert_id is not None

    accepted = client.patch(
        f"{API}/alerts/{alert_id}/accept",
        headers=headers(client, "operator01"),
    )
    assert accepted.status_code == 200
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="inside-after-alert",
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=start + timedelta(seconds=4),
    )

    with stale_threshold(300):
        data = safety(client, elder_id)

    assert data["risk_status"] == "SAFE"
    assert data["open_alert_count"] == 1
    assert data["latest_open_alert"]["status"] == "processing"


def test_tc_safety_007_and_008_family_scope_and_operator_access(
    client: TestClient,
) -> None:
    with SessionLocal() as session:
        unbound_user = User(
            username="elder-unbound-safety",
            password_hash=hash_password("demo123"),
            role="elder",
        )
        session.add(unbound_user)
        session.flush()
        unbound_elder = Elder(user_id=unbound_user.id, name="Unbound elder")
        session.add(unbound_elder)
        session.commit()
        elder_id = unbound_elder.id

    try:
        family_response = client.get(
            f"{API}/elders/{elder_id}/safety",
            headers=headers(client, "family01"),
        )
        operator_response = client.get(
            f"{API}/elders/{elder_id}/safety",
            headers=headers(client, "operator01"),
        )

        assert family_response.status_code == 404
        assert family_response.json()["error"]["code"] == "ELDER_NOT_FOUND"
        assert operator_response.status_code == 200
        assert operator_response.json()["data"]["elder_id"] == elder_id
        with SessionLocal() as session:
            family = session.scalar(select(User).where(User.username == "family01"))
            failed_read_audit = session.scalar(
                select(AuditLog).where(
                    AuditLog.action == "safety.read",
                    AuditLog.outcome == "success",
                    AuditLog.actor_user_id == family.id,
                    AuditLog.resource_id == str(elder_id),
                )
            )
        assert failed_read_audit is None
    finally:
        with SessionLocal() as session:
            elder = session.get(Elder, elder_id)
            user = session.scalar(select(User).where(User.username == "elder-unbound-safety"))
            if elder is not None:
                session.delete(elder)
                session.flush()
            if user is not None:
                session.delete(user)
            session.commit()


def test_location_health_is_conservative_without_approved_stale_threshold(
    client: TestClient,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="inside-threshold-tbd",
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=datetime.now(UTC),
    )

    with stale_threshold(None):
        data = safety(client, elder_id)

    assert data["location_health"] == "FRESHNESS_TBD"
    assert data["risk_status"] is None


def test_location_health_distinguishes_stale_and_inaccurate(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    now = datetime.now(UTC)
    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="stale-location",
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=now - timedelta(seconds=30),
    )
    with stale_threshold(10):
        stale_data = safety(client, elder_id)
    assert stale_data["location_health"] == "STALE"
    assert stale_data["risk_status"] is None

    upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id="inaccurate-location",
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=now,
        accuracy_meters=500,
    )
    with stale_threshold(10):
        inaccurate_data = safety(client, elder_id)
    assert inaccurate_data["location_health"] == "INACCURATE"
    assert inaccurate_data["risk_status"] is None


def test_safety_audit_001_authorized_family_read_is_deduplicated(
    client: TestClient,
) -> None:
    elder_id = accessible_elder_id(client)

    safety(client, elder_id, "family01")
    safety(client, elder_id, "family01")

    with SessionLocal() as session:
        family = session.scalar(select(User).where(User.username == "family01"))
        logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "safety.read",
                    AuditLog.outcome == "success",
                    AuditLog.actor_user_id == family.id,
                    AuditLog.resource_type == "elder",
                    AuditLog.resource_id == str(elder_id),
                )
            ).all()
        )

    assert len(logs) == 1


def test_safety_audit_002_authorized_operator_read_is_recorded(
    client: TestClient,
) -> None:
    elder_id = accessible_elder_id(client)

    safety(client, elder_id, "operator01")

    with SessionLocal() as session:
        operator = session.scalar(select(User).where(User.username == "operator01"))
        log = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "safety.read",
                AuditLog.outcome == "success",
                AuditLog.actor_user_id == operator.id,
                AuditLog.resource_type == "elder",
                AuditLog.resource_id == str(elder_id),
            )
        )

    assert log is not None


def test_safety_audit_003_does_not_mutate_business_records(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    start = datetime.now(UTC)
    for index in range(3):
        upload(
            client,
            elder_headers,
            trip_id=trip_id,
            client_location_id=f"outside-audit-{index}",
            latitude=23.1299,
            longitude=113.2688,
            recorded_at=start + timedelta(seconds=index),
        )
    before = business_state_snapshot()

    safety(client, elder_id, "family01")

    assert business_state_snapshot() == before


def test_safety_audit_004_failed_access_does_not_record_success(
    client: TestClient,
) -> None:
    elder_id = accessible_elder_id(client)
    unauthenticated = client.get(f"{API}/elders/{elder_id}/safety")
    missing_id = elder_id + 1_000_000
    unauthorized = client.get(
        f"{API}/elders/{missing_id}/safety",
        headers=headers(client, "family01"),
    )

    assert unauthenticated.status_code == 401
    assert unauthorized.status_code == 404
    with SessionLocal() as session:
        logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "safety.read",
                    AuditLog.outcome == "success",
                    AuditLog.resource_id.in_([str(elder_id), str(missing_id)]),
                )
            ).all()
        )
    assert logs == []
