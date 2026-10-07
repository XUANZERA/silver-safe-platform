import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.elder import Elder
from app.models.geofence import Geofence
from app.models.location import Location
from app.models.security import AuditLog
from app.models.user import User
from tests.test_auth import API
from tests.test_locations_and_risk import headers, start_trip, upload


def configure(
    client: TestClient,
    elder_id: int,
    family_headers: dict[str, str],
    *,
    radius_meters: int = 100,
    enabled: bool = True,
):
    return client.put(
        f"{API}/elders/{elder_id}/geofence",
        headers=family_headers,
        json={"radius_meters": radius_meters, "enabled": enabled},
    )


def add_real_location(
    client: TestClient,
    elder_headers: dict[str, str],
    *,
    trip_id: int,
    recorded_at: datetime | None = None,
    latitude: float = 23.1291,
    longitude: float = 113.2644,
    accuracy_meters: float | None = 10,
    source: str = "h5",
) -> None:
    response = upload(
        client,
        elder_headers,
        trip_id=trip_id,
        client_location_id=f"geofence-{datetime.now(UTC).timestamp()}",
        latitude=latitude,
        longitude=longitude,
        recorded_at=recorded_at or datetime.now(UTC),
        accuracy_meters=accuracy_meters,
        source=source,
        source_crs="WGS84",
    )
    assert response.status_code == 201


def test_geofence_write_001_family_creates_from_latest_h5_wgs84_location(
    client: TestClient,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=trip_id,
        latitude=23.125123,
        longitude=113.267456,
    )

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "elder_id": elder_id,
        "center_latitude": 23.125123,
        "center_longitude": 113.267456,
        "radius_meters": 100,
        "enabled": True,
        "crs": "WGS84",
    }


def test_geofence_write_002_updates_existing_row(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(client, elder_headers, trip_id=trip_id)
    with SessionLocal() as session:
        existing = Geofence(
            elder_id=elder_id,
            center_latitude=22.0,
            center_longitude=112.0,
            radius_meters=300,
            enabled=True,
            crs=None,
        )
        session.add(existing)
        session.commit()

    response = configure(
        client,
        elder_id,
        headers(client, "family01"),
        radius_meters=250,
        enabled=True,
    )

    assert response.status_code == 200
    assert response.json()["data"]["radius_meters"] == 250
    assert response.json()["data"]["enabled"] is True
    assert response.json()["data"]["crs"] == "WGS84"
    with SessionLocal() as session:
        assert session.scalar(select(func.count(Geofence.elder_id))) == 1
        saved = session.get(Geofence, elder_id)
        assert saved is not None
        assert saved.center_latitude == 23.1291
        assert saved.center_longitude == 113.2644


def test_geofence_write_003_family_cannot_configure_unbound_elder(
    client: TestClient,
) -> None:
    with SessionLocal() as session:
        other_user = User(
            username="unbound-elder",
            password_hash=hash_password("test-password"),
            role="elder",
        )
        session.add(other_user)
        session.flush()
        other_elder = Elder(user_id=other_user.id, name="Unbound Elder")
        session.add(other_elder)
        session.commit()
        elder_id = other_elder.id

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ELDER_NOT_FOUND"


def test_geofence_write_004_anonymous_is_rejected(client: TestClient) -> None:
    response = client.put(
        f"{API}/elders/1/geofence",
        json={"radius_meters": 100, "enabled": True},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_geofence_write_rejects_elder_and_operator_roles(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)

    for username in ("elder01", "operator01"):
        response = configure(client, elder_id, headers(client, username))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FAMILY_ROLE_REQUIRED"


def test_geofence_write_005_no_location_is_rejected(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GEOFENCE_LOCATION_NO_DATA"
    with SessionLocal() as session:
        assert session.get(Geofence, elder_id) is None


def test_geofence_write_006_legacy_null_crs_location_is_rejected(
    client: TestClient,
) -> None:
    _, trip_id, elder_id = start_trip(client)
    with SessionLocal() as session:
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="legacy-null-geofence-center",
                latitude=23.1291,
                longitude=113.2644,
                accuracy_meters=10,
                source="h5",
                source_crs=None,
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GEOFENCE_LOCATION_NO_DATA"


def test_geofence_write_rejects_simulation_location_as_center(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(client, elder_headers, trip_id=trip_id, source="simulation")

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GEOFENCE_LOCATION_NO_DATA"


def test_geofence_write_007_stale_latest_location_is_rejected(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=trip_id,
        recorded_at=datetime.now(UTC) - timedelta(seconds=61),
    )

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GEOFENCE_LOCATION_STALE"


def test_geofence_write_008_inaccurate_latest_location_is_rejected(
    client: TestClient,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=trip_id,
        accuracy_meters=101,
    )

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GEOFENCE_LOCATION_INACCURATE"


def test_geofence_write_009_and_010_radius_outside_contract_is_422(
    client: TestClient,
) -> None:
    _, _, elder_id = start_trip(client)
    family_headers = headers(client, "family01")

    below_minimum = configure(client, elder_id, family_headers, radius_meters=49)
    above_maximum = configure(client, elder_id, family_headers, radius_meters=5001)

    assert below_minimum.status_code == 422
    assert above_maximum.status_code == 422


def test_geofence_write_rejects_frontend_center_coordinates(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)
    response = client.put(
        f"{API}/elders/{elder_id}/geofence",
        headers=headers(client, "family01"),
        json={
            "radius_meters": 100,
            "enabled": True,
            "center_latitude": 23.1291,
            "center_longitude": 113.2644,
        },
    )

    assert response.status_code == 422


def test_geofence_write_011_does_not_create_alert(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(client, elder_headers, trip_id=trip_id)
    with SessionLocal() as session:
        before = session.scalar(select(func.count(Alert.id)))

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 200
    with SessionLocal() as session:
        after = session.scalar(select(func.count(Alert.id)))
    assert after == before


def test_geofence_write_013_two_puts_update_one_resource(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(client, elder_headers, trip_id=trip_id)
    family_headers = headers(client, "family01")

    first = configure(client, elder_id, family_headers, radius_meters=100)
    second = configure(client, elder_id, family_headers, radius_meters=200, enabled=False)

    assert first.status_code == second.status_code == 200
    assert second.json()["data"]["radius_meters"] == 200
    assert second.json()["data"]["enabled"] is False
    with SessionLocal() as session:
        assert session.scalar(select(func.count(Geofence.elder_id))) == 1
        assert session.get(Geofence, elder_id).radius_meters == 200


def test_geofence_write_014_success_is_audited_without_coordinates(
    client: TestClient,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(client, elder_headers, trip_id=trip_id)
    family_user = client.post(
        f"{API}/auth/login",
        json={"username": "family01", "password": "demo123"},
    ).json()["data"]["user"]

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 200
    with SessionLocal() as session:
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "geofence.configure",
                AuditLog.resource_id == str(elder_id),
            )
        )

    assert audit is not None
    assert audit.outcome == "success"
    assert audit.actor_user_id == family_user["id"]
    assert audit.details is not None
    details = json.loads(audit.details)
    assert details == {"radius_meters": 100, "enabled": True}
    assert "latitude" not in audit.details
    assert "longitude" not in audit.details


def test_geofence_uses_fresh_location_from_completed_trip(client: TestClient) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=trip_id,
        latitude=23.117777,
        longitude=113.229999,
    )
    ended = client.post(f"{API}/trips/{trip_id}/end", headers=elder_headers)
    assert ended.status_code == 200

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 200
    assert response.json()["data"]["center_latitude"] == 23.117777
    assert response.json()["data"]["center_longitude"] == 113.229999


def test_geofence_uses_completed_trip_when_current_trip_has_no_location(
    client: TestClient,
) -> None:
    elder_headers, completed_trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=completed_trip_id,
        latitude=23.118888,
        longitude=113.228888,
    )
    ended = client.post(
        f"{API}/trips/{completed_trip_id}/end",
        headers=elder_headers,
    )
    assert ended.status_code == 200

    _, current_trip_id, current_elder_id = start_trip(client)
    assert current_elder_id == elder_id

    response = configure(client, elder_id, headers(client, "family01"))

    assert current_trip_id != completed_trip_id
    assert response.status_code == 200
    assert response.json()["data"]["center_latitude"] == 23.118888
    assert response.json()["data"]["center_longitude"] == 113.228888


def test_geofence_uses_newest_eligible_location_across_elder_trips(
    client: TestClient,
) -> None:
    elder_headers, first_trip_id, elder_id = start_trip(client)
    add_real_location(
        client,
        elder_headers,
        trip_id=first_trip_id,
        latitude=23.111111,
        longitude=113.211111,
    )
    ended = client.post(f"{API}/trips/{first_trip_id}/end", headers=elder_headers)
    assert ended.status_code == 200

    second_elder_headers, second_trip_id, second_elder_id = start_trip(client)
    assert second_elder_id == elder_id
    add_real_location(
        client,
        second_elder_headers,
        trip_id=second_trip_id,
        latitude=23.222222,
        longitude=113.222222,
    )

    with SessionLocal() as session:
        first_location = session.scalar(select(Location).where(Location.trip_id == first_trip_id))
        second_location = session.scalar(select(Location).where(Location.trip_id == second_trip_id))
        assert first_location is not None and second_location is not None
        latest_time = datetime.now(UTC) - timedelta(seconds=3)
        first_location.recorded_at = latest_time
        second_location.recorded_at = latest_time - timedelta(seconds=1)
        session.commit()

    response = configure(client, elder_id, headers(client, "family01"))

    assert response.status_code == 200
    assert response.json()["data"]["center_latitude"] == 23.111111
    assert response.json()["data"]["center_longitude"] == 113.211111


@pytest.mark.parametrize("quality", ["none", "stale", "inaccurate"])
def test_disabling_existing_geofence_does_not_require_usable_location(
    client: TestClient,
    quality: str,
) -> None:
    elder_headers, trip_id, elder_id = start_trip(client)
    if quality == "stale":
        add_real_location(
            client,
            elder_headers,
            trip_id=trip_id,
            recorded_at=datetime.now(UTC) - timedelta(seconds=61),
        )
    elif quality == "inaccurate":
        add_real_location(
            client,
            elder_headers,
            trip_id=trip_id,
            accuracy_meters=101,
        )
    with SessionLocal() as session:
        session.add(
            Geofence(
                elder_id=elder_id,
                center_latitude=24.1234,
                center_longitude=114.5678,
                radius_meters=100,
                enabled=True,
                crs="WGS84",
            )
        )
        session.commit()

    response = configure(
        client,
        elder_id,
        headers(client, "family01"),
        radius_meters=200,
        enabled=False,
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "elder_id": elder_id,
        "center_latitude": 24.1234,
        "center_longitude": 114.5678,
        "radius_meters": 200,
        "enabled": False,
        "crs": "WGS84",
    }


def test_disabling_unconfigured_geofence_is_rejected(client: TestClient) -> None:
    _, _, elder_id = start_trip(client)

    response = configure(
        client,
        elder_id,
        headers(client, "family01"),
        enabled=False,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GEOFENCE_NOT_CONFIGURED"
    with SessionLocal() as session:
        assert session.get(Geofence, elder_id) is None


def test_disabling_geofence_preserves_alert_and_writes_success_audit(
    client: TestClient,
) -> None:
    _, trip_id, elder_id = start_trip(client)
    with SessionLocal() as session:
        session.add(
            Geofence(
                elder_id=elder_id,
                center_latitude=23.1291,
                center_longitude=113.2644,
                radius_meters=100,
                enabled=True,
                crs="WGS84",
            )
        )
        session.add(
            Alert(
                elder_id=elder_id,
                trip_id=trip_id,
                type="geofence_exit",
                status="new",
                latitude=23.2,
                longitude=113.3,
            )
        )
        session.commit()

    response = configure(
        client,
        elder_id,
        headers(client, "family01"),
        enabled=False,
    )

    assert response.status_code == 200
    with SessionLocal() as session:
        alert = session.scalar(select(Alert).where(Alert.elder_id == elder_id))
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "geofence.configure",
                AuditLog.resource_id == str(elder_id),
            )
        )
    assert alert is not None and alert.status == "new"
    assert audit is not None and audit.outcome == "success"
    assert json.loads(audit.details) == {"radius_meters": 100, "enabled": False}
