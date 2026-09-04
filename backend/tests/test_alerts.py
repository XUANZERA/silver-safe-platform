from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.alert import AlertLog
from app.models.location import Location
from app.models.security import AuditLog
from app.models.user import User
from tests.test_auth import API, login


def headers(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_active_trip(client: TestClient) -> tuple[int, int]:
    elder_headers = headers(client, "elder01")
    trip = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    ).json()["data"]
    started = client.post(f"{API}/trips/{trip['id']}/start", headers=elder_headers)
    assert started.status_code == 200
    return trip["id"], trip["elder_id"]


def create_sos(client: TestClient, trip_id: int):
    return client.post(
        f"{API}/alerts/sos",
        json={"trip_id": trip_id},
        headers=headers(client, "elder01"),
    )


def test_sos_deduplication_and_idempotent_operator_workflow(client: TestClient) -> None:
    trip_id, elder_id = create_active_trip(client)
    elder_headers = headers(client, "elder01")
    family_headers = headers(client, "family01")
    operator_headers = headers(client, "operator01")

    first = client.post(
        f"{API}/alerts/sos",
        json={"trip_id": trip_id},
        headers=elder_headers,
    )
    duplicate = client.post(
        f"{API}/alerts/sos",
        json={"trip_id": trip_id},
        headers=elder_headers,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["id"] == first.json()["data"]["id"]
    alert_id = first.json()["data"]["id"]
    assert first.json()["data"]["latitude"] is None

    family_list = client.get(
        f"{API}/elders/{elder_id}/alerts",
        headers=family_headers,
    )
    operator_list = client.get(
        f"{API}/alerts?status=new&type=emergency&page=1&page_size=10",
        headers=operator_headers,
    )
    forbidden_accept = client.patch(
        f"{API}/alerts/{alert_id}/accept",
        headers=family_headers,
    )

    assert family_list.json()["data"]["total"] == 1
    assert operator_list.json()["data"]["total"] == 1
    assert operator_list.json()["data"]["has_more"] is False
    assert forbidden_accept.status_code == 403
    assert forbidden_accept.json()["error"]["code"] == "OPERATOR_REQUIRED"

    accepted = client.patch(
        f"{API}/alerts/{alert_id}/accept",
        headers=operator_headers,
    )
    repeated_accept = client.patch(
        f"{API}/alerts/{alert_id}/accept",
        headers=operator_headers,
    )
    resolved = client.patch(
        f"{API}/alerts/{alert_id}/resolve",
        json={"resolution": "已联系老人，确认安全"},
        headers=operator_headers,
    )
    repeated_resolve = client.patch(
        f"{API}/alerts/{alert_id}/resolve",
        json={"resolution": "已联系老人，确认安全"},
        headers=operator_headers,
    )

    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "processing"
    assert repeated_accept.status_code == 200
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"
    assert repeated_resolve.status_code == 200

    detail = client.get(
        f"{API}/alerts/{alert_id}",
        headers=family_headers,
    ).json()["data"]
    assert [log["action"] for log in detail["logs"]] == ["accepted", "resolved"]
    assert detail["alert"]["handler"]["username"] == "operator01"


def test_alert_must_be_accepted_before_resolution(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    alert_id = create_sos(client, trip_id).json()["data"]["id"]
    response = client.patch(
        f"{API}/alerts/{alert_id}/resolve",
        json={"resolution": "老人安全"},
        headers=headers(client, "operator01"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALERT_NOT_ACCEPTED"


def test_tc_sos_002_requires_an_active_trip(client: TestClient) -> None:
    elder_headers = headers(client, "elder01")
    trip = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    ).json()["data"]

    response = client.post(
        f"{API}/alerts/sos",
        json={"trip_id": trip["id"]},
        headers=elder_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ACTIVE_TRIP"


def test_sos_rate_limit_blocks_fourth_request_with_retry_after(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    elder_headers = headers(client, "elder01")
    responses = [
        client.post(
            f"{API}/alerts/sos",
            json={"trip_id": trip_id},
            headers=elder_headers,
        )
        for _ in range(4)
    ]
    assert [response.status_code for response in responses[:3]] == [201, 200, 200]
    assert responses[3].status_code == 429
    assert responses[3].json()["error"]["code"] == "SOS_RATE_LIMITED"
    assert responses[3].headers["retry-after"] == "60"


def test_authenticated_non_elder_sos_misuse_is_also_rate_limited(client: TestClient) -> None:
    family_headers = headers(client, "family01")
    responses = [
        client.post(
            f"{API}/alerts/sos",
            json={"trip_id": 999999},
            headers=family_headers,
        )
        for _ in range(4)
    ]
    assert [response.status_code for response in responses[:3]] == [403, 403, 403]
    assert all(
        response.json()["error"]["code"] == "ELDER_ROLE_REQUIRED" for response in responses[:3]
    )
    assert responses[3].status_code == 429
    assert responses[3].json()["error"]["code"] == "SOS_RATE_LIMITED"


def test_concurrent_sos_requests_are_serialized(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    elder_headers = headers(client, "elder01")

    def request_sos(_: int):
        return client.post(
            f"{API}/alerts/sos",
            json={"trip_id": trip_id},
            headers=elder_headers,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(request_sos, range(4)))

    assert sorted(response.status_code for response in responses) == [200, 200, 201, 429]
    alert_ids = {
        response.json()["data"]["id"]
        for response in responses
        if response.status_code in {200, 201}
    }
    assert len(alert_ids) == 1


def test_alert_detail_does_not_leak_other_elder_event_existence(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    alert_id = create_sos(client, trip_id).json()["data"]["id"]
    with SessionLocal() as session:
        if session.scalar(select(User).where(User.username == "family02")) is None:
            session.add(
                User(
                    username="family02",
                    password_hash=hash_password("family02-password"),
                    role="family",
                )
            )
            session.commit()

    family_token = client.post(
        f"{API}/auth/login",
        json={"username": "family02", "password": "family02-password"},
    ).json()["data"]["access_token"]

    response = client.get(
        f"{API}/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {family_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ALERT_NOT_FOUND"


def test_sensitive_alert_polling_audit_is_window_deduplicated(client: TestClient) -> None:
    trip_id, elder_id = create_active_trip(client)
    create_sos(client, trip_id)
    family_headers = headers(client, "family01")
    for _ in range(3):
        response = client.get(
            f"{API}/elders/{elder_id}/alerts",
            headers=family_headers,
        )
        assert response.status_code == 200

    with SessionLocal() as session:
        logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "alert.list.read",
                    AuditLog.actor_user_id.is_not(None),
                    AuditLog.resource_id == str(elder_id),
                )
            )
        )
    assert len(logs) == 1


def test_alert_indexes_support_dashboard_queries() -> None:
    indexes = {item["name"] for item in inspect(engine).get_indexes("alerts")}
    assert "ix_alerts_occurred" in indexes
    assert "ix_alerts_status_occurred" in indexes
    assert "ix_alerts_status_type_occurred" in indexes
    assert "ix_alerts_elder_status_occurred" in indexes
    assert "ix_alerts_trip_type_status" in indexes

    with engine.connect() as connection:
        status_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM alerts "
                "WHERE status = 'new' ORDER BY occurred_at DESC LIMIT 20"
            )
        ).all()
        typed_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM alerts "
                "WHERE status = 'new' AND type = 'emergency' "
                "ORDER BY occurred_at DESC LIMIT 20"
            )
        ).all()
        audit_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM audit_logs "
                "WHERE actor_user_id = 1 AND action = 'alert.list.read' "
                "AND outcome = 'success' AND resource_type = 'elder' "
                "AND resource_id = '1' AND occurred_at >= '2026-01-01' LIMIT 1"
            )
        ).all()

    status_text = " ".join(str(column) for row in status_plan for column in row)
    typed_text = " ".join(str(column) for row in typed_plan for column in row)
    audit_text = " ".join(str(column) for row in audit_plan for column in row)
    assert "ix_alerts_status_occurred" in status_text
    assert "ix_alerts_status_type_occurred" in typed_text
    assert "USING INDEX" in audit_text
    assert any(
        name in audit_text for name in ("ix_audit_actor_action_time", "ix_audit_resource_time")
    )


def test_alert_logs_contain_only_real_state_changes(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    alert_id = create_sos(client, trip_id).json()["data"]["id"]
    operator_headers = headers(client, "operator01")
    for _ in range(2):
        client.patch(f"{API}/alerts/{alert_id}/accept", headers=operator_headers)
    for _ in range(2):
        client.patch(
            f"{API}/alerts/{alert_id}/resolve",
            json={"resolution": "已确认安全"},
            headers=operator_headers,
        )

    with SessionLocal() as session:
        actions = list(
            session.scalars(
                select(AlertLog.action).where(AlertLog.alert_id == alert_id).order_by(AlertLog.id)
            )
        )
    assert actions == ["accepted", "resolved"]


def test_concurrent_operators_cannot_both_accept_one_alert(client: TestClient) -> None:
    with SessionLocal() as session:
        operator = session.scalar(select(User).where(User.username == "operator02"))
        if operator is None:
            session.add(
                User(
                    username="operator02",
                    password_hash=hash_password("operator02-password"),
                    role="operator",
                )
            )
            session.commit()

    trip_id, _ = create_active_trip(client)
    alert_id = create_sos(client, trip_id).json()["data"]["id"]
    first_headers = headers(client, "operator01")
    second_token = client.post(
        f"{API}/auth/login",
        json={"username": "operator02", "password": "operator02-password"},
    ).json()["data"]["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}
    barrier = Barrier(2)

    def accept(auth_headers: dict[str, str]):
        barrier.wait()
        return client.patch(f"{API}/alerts/{alert_id}/accept", headers=auth_headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(accept, (first_headers, second_headers)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    with SessionLocal() as session:
        logs = list(
            session.scalars(
                select(AlertLog).where(
                    AlertLog.alert_id == alert_id,
                    AlertLog.action == "accepted",
                )
            )
        )
    assert len(logs) == 1


def test_openapi_contains_only_expected_alert_operations(client: TestClient) -> None:
    paths = client.get(f"{API}/openapi.json").json()["paths"]
    assert f"{API}/alerts/sos" in paths
    assert f"{API}/elders/{{elder_id}}/alerts" in paths
    assert f"{API}/alerts" in paths
    assert f"{API}/alerts/{{alert_id}}" in paths
    assert f"{API}/alerts/{{alert_id}}/accept" in paths
    assert f"{API}/alerts/{{alert_id}}/resolve" in paths
    assert f"{API}/ai/chat" in paths
    assert f"{API}/elders/{{elder_id}}/safety" in paths
    operations = sum(
        method in {"get", "post", "put", "patch", "delete"}
        for path in paths.values()
        for method in path
    )
    assert operations == 25


def test_sos_does_not_consume_legacy_null_crs_location(client: TestClient) -> None:
    trip_id, _ = create_active_trip(client)
    with SessionLocal() as session:
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="legacy-null-crs",
                latitude=23.1291,
                longitude=113.2644,
                source="simulation",
                source_crs=None,
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()

    response = create_sos(client, trip_id)
    assert response.status_code == 201
    alert_data = response.json()["data"]
    assert alert_data["latitude"] is None
    assert alert_data["longitude"] is None


def test_sos_uses_canonical_wgs84_location_when_legacy_location_is_newer(
    client: TestClient,
) -> None:
    trip_id, _ = create_active_trip(client)
    now = datetime.now(UTC)
    with SessionLocal() as session:
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="wgs84-older",
                latitude=39.9042,
                longitude=116.4074,
                source="h5",
                source_crs="WGS84",
                recorded_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="legacy-newer",
                latitude=23.1291,
                longitude=113.2644,
                source="simulation",
                source_crs=None,
                recorded_at=now,
            )
        )
        session.commit()

    response = create_sos(client, trip_id)
    assert response.status_code == 201
    alert_data = response.json()["data"]
    assert alert_data["latitude"] == 39.9042
    assert alert_data["longitude"] == 116.4074


def test_sos_uses_latest_canonical_wgs84_location_when_canonical_is_newer(
    client: TestClient,
) -> None:
    trip_id, _ = create_active_trip(client)
    now = datetime.now(UTC)
    with SessionLocal() as session:
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="legacy-older",
                latitude=23.1291,
                longitude=113.2644,
                source="simulation",
                source_crs=None,
                recorded_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            Location(
                trip_id=trip_id,
                client_location_id="wgs84-newer",
                latitude=39.9042,
                longitude=116.4074,
                source="h5",
                source_crs="WGS84",
                recorded_at=now,
            )
        )
        session.commit()

    response = create_sos(client, trip_id)
    assert response.status_code == 201
    alert_data = response.json()["data"]
    assert alert_data["latitude"] == 39.9042
    assert alert_data["longitude"] == 116.4074
