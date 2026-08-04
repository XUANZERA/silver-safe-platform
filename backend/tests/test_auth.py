import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.user import User

API = "/api/v1"


def login(client: TestClient, username: str, password: str = "demo123") -> dict:
    response = client.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.parametrize(
    ("username", "role"),
    [
        ("elder01", "elder"),
        ("family01", "family"),
        ("operator01", "operator"),
    ],
)
def test_demo_accounts_can_login(
    client: TestClient,
    username: str,
    role: str,
) -> None:
    data = login(client, username)

    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 7200
    assert data["user"]["role"] == role


def test_password_is_hashed_in_database(client: TestClient) -> None:
    login(client, "elder01")
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == "elder01"))

    assert user is not None
    assert user.password_hash != "demo123"
    assert user.password_hash.startswith("$argon2")


def test_login_rejects_invalid_password(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/login",
        json={"username": "elder01", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "用户名或密码错误",
        },
    }


def test_me_requires_and_restores_login(client: TestClient) -> None:
    unauthorized = client.get(f"{API}/auth/me")
    token = login(client, "family01")["access_token"]
    authorized = client.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
    assert authorized.status_code == 200
    assert authorized.json()["data"]["username"] == "family01"


def test_refresh_rotation_and_logout_revocation(client: TestClient) -> None:
    login(client, "elder01")
    first_refresh = client.cookies.get("silver_safe_refresh")
    assert first_refresh is not None

    refreshed = client.post(f"{API}/auth/refresh")
    assert refreshed.status_code == 200
    refreshed_data = refreshed.json()["data"]
    second_refresh = client.cookies.get("silver_safe_refresh")
    assert second_refresh is not None and second_refresh != first_refresh
    assert "refresh_token" not in refreshed_data

    logout = client.post(
        f"{API}/auth/logout",
        headers={
            "Authorization": f"Bearer {refreshed_data['access_token']}",
        },
    )
    assert logout.status_code == 200

    revoked = client.get(
        f"{API}/auth/me",
        headers={
            "Authorization": f"Bearer {refreshed_data['access_token']}",
        },
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "SESSION_REVOKED"


def test_reused_refresh_token_revokes_session(client: TestClient) -> None:
    login(client, "elder01")
    first_refresh = client.cookies.get("silver_safe_refresh")
    assert first_refresh is not None
    rotated = client.post(f"{API}/auth/refresh").json()["data"]

    client.cookies.set("silver_safe_refresh", first_refresh)
    reused = client.post(f"{API}/auth/refresh")
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"

    revoked = client.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "SESSION_REVOKED"


def test_refresh_token_is_http_only_cookie(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/login",
        json={"username": "elder01", "password": "demo123"},
    )

    cookie = response.headers["set-cookie"].lower()
    assert "silver_safe_refresh=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "refresh_token" not in response.json()["data"]


def test_frontend_origin_can_send_credentials(client: TestClient) -> None:
    response = client.options(
        f"{API}/auth/refresh",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="local-development-only-change-me-2026",
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="a-strong-production-secret-key-2026",
            health_info_encryption_key="local-health-info-key-change-me-2026",
        )
