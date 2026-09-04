from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.elder import Elder
from app.models.trip import Trip
from app.services.trips import create_trip, start_trip
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


@pytest.mark.parametrize("destination", ["", "   ", "暂无行程", " 暂无真实行程 "])
def test_trip_destination_rejects_empty_and_reserved_values(
    client: TestClient,
    destination: str,
) -> None:
    response = client.post(
        f"{API}/trips",
        json={"destination": destination},
        headers=auth_header(client, "elder01"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        (" 人民公园 ", "人民公园"),
        ("行" * 200, "行" * 200),
        (f" {'行' * 200} ", "行" * 200),
    ],
)
def test_trip_destination_accepts_valid_values_up_to_200_trimmed_characters(
    client: TestClient,
    destination: str,
    expected: str,
) -> None:
    response = client.post(
        f"{API}/trips",
        json={"destination": destination},
        headers=auth_header(client, "elder01"),
    )

    assert response.status_code == 201
    assert response.json()["data"]["destination"] == expected


def test_trip_destination_rejects_201_characters(client: TestClient) -> None:
    response = client.post(
        f"{API}/trips",
        json={"destination": "行" * 201},
        headers=auth_header(client, "elder01"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_trip_ignores_injected_elder_id(client: TestClient) -> None:
    elder_headers = auth_header(client, "elder01")
    owned_elder = client.get(f"{API}/elders", headers=elder_headers).json()["data"]["items"][0]

    response = client.post(
        f"{API}/trips",
        json={"destination": "人民公园", "elder_id": owned_elder["id"] + 9999},
        headers=elder_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["elder_id"] == owned_elder["id"]


def test_concurrent_create_leaves_at_most_one_unfinished_trip(client: TestClient) -> None:
    auth_header(client, "elder01")
    barrier = Barrier(2)

    def create() -> str:
        with SessionLocal() as session:
            elder = session.scalar(
                select(Elder).join(Elder.user).where(Elder.user.has(username="elder01"))
            )
            assert elder is not None
            barrier.wait()
            try:
                create_trip(session, elder, "人民公园")
            except AppError as error:
                assert error.status_code == 409
                assert error.error_code == "UNFINISHED_TRIP_EXISTS"
                return "conflict"
            return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))

    assert sorted(results) == ["conflict", "created"]
    with SessionLocal() as session:
        unfinished_count = session.scalar(
            select(func.count(Trip.id)).where(Trip.status.in_(("created", "active")))
        )
    assert unfinished_count == 1


def test_concurrent_start_allows_one_transition_and_finishes_active(client: TestClient) -> None:
    elder_headers = auth_header(client, "elder01")
    trip_id = client.post(
        f"{API}/trips",
        json={"destination": "人民公园"},
        headers=elder_headers,
    ).json()["data"]["id"]
    barrier = Barrier(2)

    def start() -> str:
        with SessionLocal() as session:
            trip = session.get(Trip, trip_id)
            assert trip is not None
            barrier.wait()
            try:
                start_trip(session, trip)
            except AppError as error:
                assert error.status_code == 409
                assert error.error_code == "TRIP_ALREADY_STARTED"
                return "conflict"
            return "started"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: start(), range(2)))

    assert sorted(results) == ["conflict", "started"]
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)
        assert trip is not None
        assert trip.status == "active"
        assert trip.started_at is not None
