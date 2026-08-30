from fastapi.testclient import TestClient

from tests.test_auth import API, login

TIME_FIELDS = ("created_at", "started_at", "ended_at", "cancelled_at")


def auth_header(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def assert_utc_times(trip: dict[str, object]) -> None:
    for field in TIME_FIELDS:
        value = trip[field]
        if value is not None:
            assert isinstance(value, str)
            assert "T" in value
            assert value.endswith("Z")


def test_trip_lifecycle_and_permissions(client: TestClient) -> None:
    elder_headers = auth_header(client, "elder01")
    family_headers = auth_header(client, "family01")
    operator_headers = auth_header(client, "operator01")

    created = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    )
    assert created.status_code == 201
    trip = created.json()["data"]
    trip_id = trip["id"]
    elder_id = trip["elder_id"]
    assert trip["status"] == "created"
    assert_utc_times(trip)

    current_created = client.get(
        f"{API}/elders/{elder_id}/current-trip",
        headers=family_headers,
    )
    assert current_created.json()["data"]["status"] == "created"

    duplicate = client.post(
        f"{API}/trips",
        json={"destination": "社区服务中心"},
        headers=elder_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "UNFINISHED_TRIP_EXISTS"

    assert client.get(f"{API}/trips/{trip_id}", headers=family_headers).status_code == 200
    assert client.get(f"{API}/trips/{trip_id}", headers=operator_headers).status_code == 200
    assert client.post(f"{API}/trips/{trip_id}/start", headers=family_headers).status_code == 403

    started = client.post(f"{API}/trips/{trip_id}/start", headers=elder_headers)
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "active"
    assert_utc_times(started.json()["data"])

    repeated_start = client.post(f"{API}/trips/{trip_id}/start", headers=elder_headers)
    assert repeated_start.status_code == 409
    assert repeated_start.json()["error"]["code"] == "TRIP_ALREADY_STARTED"

    ended = client.post(f"{API}/trips/{trip_id}/end", headers=elder_headers)
    assert ended.status_code == 200
    assert ended.json()["data"]["status"] == "completed"
    assert_utc_times(ended.json()["data"])

    repeated_end = client.post(f"{API}/trips/{trip_id}/end", headers=elder_headers)
    assert repeated_end.status_code == 409
    assert repeated_end.json()["error"]["code"] == "TRIP_ALREADY_COMPLETED"

    no_current_trip = client.get(
        f"{API}/elders/{elder_id}/current-trip",
        headers=family_headers,
    )
    assert no_current_trip.status_code == 200
    assert no_current_trip.json()["data"] is None


def test_created_trip_can_be_cancelled(client: TestClient) -> None:
    elder_headers = auth_header(client, "elder01")
    trip = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    ).json()["data"]

    cancelled = client.post(
        f"{API}/trips/{trip['id']}/cancel",
        json={"reason": "临时取消"},
        headers=elder_headers,
    )

    assert cancelled.status_code == 200
    data = cancelled.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancel_reason"] == "临时取消"
    assert data["cancelled_at"] is not None
    assert_utc_times(data)


def test_non_elder_cannot_create_trip(client: TestClient) -> None:
    response = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=auth_header(client, "family01"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ELDER_ROLE_REQUIRED"
