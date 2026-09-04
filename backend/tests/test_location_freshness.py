from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

import app.services.safety as safety_service
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.location import Location
from app.models.security import AuditLog
from app.models.trip import Trip
from tests.test_auth import API
from tests.test_locations_and_risk import headers, start_trip, upload


@contextmanager
def stale_threshold(seconds: int):
    settings = get_settings()
    original = settings.location_stale_after_seconds
    try:
        settings.location_stale_after_seconds = seconds
        yield
    finally:
        settings.location_stale_after_seconds = original


def freeze_safety_time(monkeypatch: pytest.MonkeyPatch, instant: datetime) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant.astimezone(UTC).replace(tzinfo=None)
            return instant.astimezone(tz)

    monkeypatch.setattr(safety_service, "datetime", FrozenDateTime)


def get_safety(client: TestClient, elder_id: int) -> dict:
    response = client.get(
        f"{API}/elders/{elder_id}/safety",
        headers=headers(client, "family01"),
    )
    assert response.status_code == 200
    return response.json()["data"]


def upload_location(
    client: TestClient,
    elder_headers: dict[str, str],
    *,
    trip_id: int,
    recorded_at: datetime,
    client_location_id: str,
    accuracy_meters: float = 10,
) -> None:
    response = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id=client_location_id,
        latitude=23.1291,
        longitude=113.2644,
        recorded_at=recorded_at,
        accuracy_meters=accuracy_meters,
    )
    assert response.status_code == 201


def freshness_business_state_snapshot() -> dict[str, tuple[int, list[tuple[object, ...]]]]:
    with SessionLocal() as session:
        trips = list(session.scalars(select(Trip).order_by(Trip.id)).all())
        locations = list(session.scalars(select(Location).order_by(Location.id)).all())
        alerts = list(session.scalars(select(Alert).order_by(Alert.id)).all())
        return {
            "trips": (
                len(trips),
                [
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
            ),
            "locations": (
                len(locations),
                [
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
            ),
            "alerts": (
                len(alerts),
                [
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
            ),
        }


def test_fresh_001_no_canonical_location_returns_no_data(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)

    data = get_safety(client, elder_id)

    assert data["location_health"] == "NO_DATA"
    assert data["latest_location"] is None


def test_fresh_002_threshold_minus_one_is_fresh(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    recorded_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="fresh-minus-one",
    )
    freeze_safety_time(monkeypatch, recorded_at + timedelta(seconds=59))

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "FRESH"


def test_fresh_003_exact_threshold_is_fresh(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    recorded_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="fresh-boundary",
    )
    freeze_safety_time(monkeypatch, recorded_at + timedelta(seconds=60))

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "FRESH"


def test_fresh_004_threshold_plus_one_is_stale_before_accuracy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    recorded_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="stale-boundary",
        accuracy_meters=500,
    )
    freeze_safety_time(monkeypatch, recorded_at + timedelta(seconds=61))

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "STALE"
    assert data["risk_status"] is None


def test_fresh_005_legacy_null_crs_is_ignored(client: TestClient) -> None:
    _, trip_id, elder_id = start_trip(client)
    with SessionLocal() as session:
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="legacy-null-crs",
                latitude=23.1291,
                longitude=113.2644,
                accuracy_meters=10,
                source="h5",
                source_crs=None,
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()

    data = get_safety(client, elder_id)

    assert data["location_health"] == "NO_DATA"
    assert data["latest_location"] is None


def test_fresh_006_stale_safety_get_only_writes_privacy_audit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    recorded_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="stale-read-only",
    )
    auth_headers = headers(client, "family01")
    freeze_safety_time(monkeypatch, recorded_at + timedelta(seconds=61))
    before_business_state = freshness_business_state_snapshot()
    with SessionLocal() as session:
        before_safety_audits = session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.action == "safety.read")
        )

    with stale_threshold(60):
        response = client.get(f"{API}/elders/{elder_id}/safety", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["location_health"] == "STALE"
    after_business_state = freshness_business_state_snapshot()
    with SessionLocal() as session:
        after_safety_audits = session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.action == "safety.read")
        )

    assert after_business_state == before_business_state
    assert after_safety_audits == before_safety_audits + 1


def test_fresh_007_new_latest_location_restores_fresh(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    calculated_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=calculated_at - timedelta(seconds=61),
        client_location_id="old-location",
    )
    freeze_safety_time(monkeypatch, calculated_at)
    with stale_threshold(60):
        assert get_safety(client, elder_id)["location_health"] == "STALE"

        upload_location(
            client,
            elder_headers,
            trip_id=trip_id,
            recorded_at=calculated_at,
            client_location_id="new-location",
        )
        recovered = get_safety(client, elder_id)

    assert recovered["location_health"] == "FRESH"
    assert recovered["latest_location"]["client_location_id"] == "new-location"


def test_fresh_008_timezone_aware_timestamp_is_compared_in_utc(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    utc_recorded_at = datetime.now(UTC)
    recorded_at = utc_recorded_at.astimezone(timezone(timedelta(hours=8)))
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="timezone-aware",
    )
    freeze_safety_time(monkeypatch, utc_recorded_at + timedelta(seconds=30))

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "FRESH"
    assert data["latest_location"]["recorded_at"].endswith("Z")
    assert data["calculated_at"].endswith("Z")


def test_fresh_009_slightly_future_timestamp_clamps_age_to_zero(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    calculated_at = datetime.now(UTC)
    recorded_at = calculated_at + timedelta(seconds=1)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="slightly-future",
    )
    freeze_safety_time(monkeypatch, calculated_at)

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "FRESH"


def test_fresh_010_inaccurate_behavior_is_preserved(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    recorded_at = datetime.now(UTC)
    upload_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=recorded_at,
        client_location_id="fresh-inaccurate",
        accuracy_meters=500,
    )
    freeze_safety_time(monkeypatch, recorded_at + timedelta(seconds=30))

    with stale_threshold(60):
        data = get_safety(client, elder_id)

    assert data["location_health"] == "INACCURATE"
    assert data["risk_status"] is None


def test_location_stale_threshold_defaults_to_sixty_seconds() -> None:
    assert Settings(_env_file=None).location_stale_after_seconds == 60


def test_location_stale_threshold_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, location_stale_after_seconds=0)


def test_location_stale_threshold_rejects_negative_one() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, location_stale_after_seconds=-1)


def test_location_stale_threshold_rejects_above_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, location_stale_after_seconds=86401)
