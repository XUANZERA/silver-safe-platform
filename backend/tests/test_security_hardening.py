from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import DUMMY_PASSWORD_HASH, verify_password
from app.db.session import SessionLocal
from app.models.security import AuditLog
from app.services.audit import client_ip
from app.services.auth_sessions import rotate_refresh_token
from tests.test_auth import API, login


def test_unknown_user_uses_dummy_hash_and_audit_is_pseudonymous(client: TestClient) -> None:
    username = "missing-user.forged-log-line"
    with patch(
        "app.api.routes.auth.verify_password",
        wraps=verify_password,
    ) as password_check:
        response = client.post(
            f"{API}/auth/login",
            json={"username": username, "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert password_check.call_args.args[1] == DUMMY_PASSWORD_HASH

    with SessionLocal() as session:
        audit = session.scalar(
            select(AuditLog)
            .where(AuditLog.action == "auth.login", AuditLog.outcome == "failure")
            .order_by(AuditLog.id.desc())
        )

    assert audit is not None
    assert audit.resource_type == "login_subject"
    assert len(audit.resource_id or "") == 64
    assert username not in (audit.details or "")


def test_login_failures_are_rate_limited(client: TestClient) -> None:
    settings = get_settings()
    for _ in range(settings.login_failure_per_username):
        response = client.post(
            f"{API}/auth/login",
            json={"username": "elder01", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = client.post(
        f"{API}/auth/login",
        json={"username": "elder01", "password": "demo123"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "LOGIN_RATE_LIMITED"


def test_concurrent_login_failures_cannot_bypass_limit(client: TestClient) -> None:
    settings = get_settings()
    attempts = settings.login_failure_per_username + 3
    barrier = Barrier(attempts)

    def attempt_login() -> int:
        barrier.wait()
        return client.post(
            f"{API}/auth/login",
            json={"username": "family01", "password": "wrong-password"},
        ).status_code

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        statuses = list(executor.map(lambda _: attempt_login(), range(attempts)))

    assert statuses.count(401) == settings.login_failure_per_username
    assert statuses.count(429) == attempts - settings.login_failure_per_username


def test_refresh_rotation_allows_only_one_concurrent_winner(client: TestClient) -> None:
    login(client, "elder01")
    refresh_token = client.cookies.get("silver_safe_refresh")
    assert refresh_token is not None
    barrier = Barrier(2)

    def attempt_rotation() -> str:
        with SessionLocal() as session:
            barrier.wait()
            try:
                rotate_refresh_token(session, refresh_token)
                session.commit()
                return "success"
            except AppError as exc:
                return exc.error_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt_rotation(), range(2)))

    assert results.count("success") == 1
    assert results.count("REFRESH_TOKEN_REUSED") == 1


def _request(*, peer: str, forwarded: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-real-ip", forwarded.encode("ascii"))],
            "client": (peer, 12345),
        }
    )


def test_proxy_header_is_used_only_for_trusted_peer() -> None:
    settings = get_settings()
    original = settings.trusted_proxy_networks
    try:
        settings.trusted_proxy_networks = []
        assert client_ip(_request(peer="203.0.113.10", forwarded="198.51.100.9")) == (
            "203.0.113.10"
        )

        settings.trusted_proxy_networks = ["10.0.0.0/8"]
        assert client_ip(_request(peer="10.1.2.3", forwarded="198.51.100.9")) == ("198.51.100.9")
        assert client_ip(_request(peer="10.1.2.3", forwarded="not-an-ip")) == "10.1.2.3"
    finally:
        settings.trusted_proxy_networks = original


def test_invalid_trusted_proxy_network_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trusted_proxy_networks=["not-a-network"])


def test_logout_is_idempotent_without_access_token(client: TestClient) -> None:
    logged_in = login(client, "elder01")
    response = client.post(f"{API}/auth/logout")

    assert response.status_code == 200
    assert client.cookies.get("silver_safe_refresh") is None
    revoked = client.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "SESSION_REVOKED"

    repeated = client.post(f"{API}/auth/logout")
    assert repeated.status_code == 200
