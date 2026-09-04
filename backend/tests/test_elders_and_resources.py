from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.elder import Elder
from app.models.geofence import Geofence
from app.models.security import AuditLog
from tests.test_auth import API, login


def headers(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_role_scoped_elder_queries_and_geofence(client: TestClient) -> None:
    elder_response = client.get(f"{API}/elders", headers=headers(client, "elder01"))
    family_response = client.get(f"{API}/elders", headers=headers(client, "family01"))
    operator_response = client.get(f"{API}/elders", headers=headers(client, "operator01"))

    for response in (elder_response, family_response, operator_response):
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 1
        assert response.json()["data"]["items"][0]["name"] == "王奶奶"

    elder_id = family_response.json()["data"]["items"][0]["id"]
    detail = client.get(f"{API}/elders/{elder_id}", headers=headers(client, "family01"))
    geofence = client.get(
        f"{API}/elders/{elder_id}/geofence",
        headers=headers(client, "family01"),
    )

    assert detail.status_code == 200
    assert detail.json()["data"]["health_info"] == "轻度高血压"
    assert geofence.status_code == 200
    assert geofence.json()["data"] is None
    assert geofence.json()["message"] == "暂未配置安全围栏"

    with SessionLocal() as session:
        session.add(
            Geofence(
                elder_id=elder_id,
                center_latitude=23.1300,
                center_longitude=113.2600,
                radius_meters=300,
                enabled=True,
                crs="WGS84",
            )
        )
        session.commit()

    configured = client.get(
        f"{API}/elders/{elder_id}/geofence",
        headers=headers(client, "family01"),
    )
    assert configured.status_code == 200
    assert configured.json()["data"]["radius_meters"] == 300
    assert configured.json()["data"]["center_latitude"] == 23.1300
    assert configured.json()["data"]["center_longitude"] == 113.2600
    assert configured.json()["data"]["crs"] == "WGS84"
    assert "id" not in configured.json()["data"]


def test_health_info_is_encrypted_redacted_and_audited(client: TestClient) -> None:
    family_headers = headers(client, "family01")
    operator_headers = headers(client, "operator01")
    elder_id = client.get(f"{API}/elders", headers=family_headers).json()["data"]["items"][0]["id"]

    family_view = client.get(f"{API}/elders/{elder_id}", headers=family_headers)
    operator_view = client.get(f"{API}/elders/{elder_id}", headers=operator_headers)

    assert family_view.json()["data"]["health_info"] == "轻度高血压"
    assert operator_view.json()["data"]["health_info"] is None

    with SessionLocal() as session:
        stored = session.scalar(select(Elder.health_info).where(Elder.id == elder_id))
        audit_outcomes = list(
            session.scalars(
                select(AuditLog.outcome)
                .where(
                    AuditLog.action == "health_info.read",
                    AuditLog.resource_id == str(elder_id),
                )
                .order_by(AuditLog.id)
            )
        )

    assert stored is not None and stored.startswith("enc:v1:")
    assert "轻度高血压" not in stored
    assert "success" in audit_outcomes
    assert "redacted" in audit_outcomes


def test_out_of_scope_endpoints_are_not_exposed(client: TestClient) -> None:
    elder_headers = headers(client, "elder01")

    assert client.get(f"{API}/service-points", headers=elder_headers).status_code == 404
    assert client.post(f"{API}/routes/recommend", headers=elder_headers).status_code == 404
    assert client.post(f"{API}/risk-events", headers=elder_headers).status_code == 404
