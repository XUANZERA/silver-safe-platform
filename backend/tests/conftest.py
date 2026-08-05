import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

TEST_DATABASE = Path(__file__).resolve().parents[2] / "data" / "test_silver_safe.db"
TEST_DATABASE.parent.mkdir(parents=True, exist_ok=True)
TEST_DATABASE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///./data/test_silver_safe.db"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_business_data(client: TestClient) -> Iterator[None]:
    from app.db.session import SessionLocal
    from app.models.security import AuditLog, AuthSession
    from app.models.trip import Trip

    with SessionLocal() as session:
        session.execute(delete(AuditLog))
        session.execute(delete(AuthSession))
        session.execute(delete(Trip))
        session.commit()
    yield


def pytest_sessionfinish() -> None:
    from app.db.session import engine

    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)
