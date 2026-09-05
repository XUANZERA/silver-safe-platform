import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import Settings
from app.core.security import verify_password
from app.db.base import Base
from app.models.elder import Elder, ElderFamilyBinding
from app.models.trip import Trip
from app.models.user import User
from app.services.seed import (
    TEST_ELDER_USERNAME,
    TEST_FAMILY_USERNAME,
    TEST_TRIP_DESTINATION,
    seed_environment_data,
)

PUBLIC_SETTINGS = {
    "debug": False,
    "secret_key": "testing-jwt-signing-key-2026-long-enough",
    "health_info_encryption_key": "testing-health-encryption-key-2026-separate",
}


def test_testing_settings_require_an_isolated_database_and_account_password() -> None:
    with pytest.raises(ValidationError, match="独立 DATABASE_URL"):
        Settings(
            _env_file=None,
            app_env="testing",
            database_url="sqlite:///./data/silver_safe.db",
            test_account_password="volunteer-secret",
            **PUBLIC_SETTINGS,
        )

    with pytest.raises(ValidationError, match="TEST_ACCOUNT_PASSWORD"):
        Settings(
            _env_file=None,
            app_env="testing",
            database_url="sqlite:///./data/volunteer_test.db",
            test_account_password=None,
            **PUBLIC_SETTINGS,
        )


def test_testing_settings_use_secure_cookies() -> None:
    settings = Settings(
        _env_file=None,
        app_env="testing",
        database_url="sqlite:///./data/volunteer_test.db",
        test_account_password="volunteer-secret",
        **PUBLIC_SETTINGS,
    )

    assert settings.secure_cookies is True


def test_testing_seed_creates_required_accounts_binding_and_active_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_environment_data(
            session,
            app_env="testing",
            test_account_password="volunteer-secret",
        )
        # Initialization is idempotent across service restarts.
        seed_environment_data(
            session,
            app_env="testing",
            test_account_password="volunteer-secret",
        )

        users = session.scalars(select(User).order_by(User.username)).all()
        elder = session.scalar(select(Elder))
        binding = session.scalar(select(ElderFamilyBinding))
        trips = session.scalars(select(Trip)).all()

    assert [(user.username, user.role) for user in users] == [
        (TEST_ELDER_USERNAME, "elder"),
        (TEST_FAMILY_USERNAME, "family"),
    ]
    assert all(user.phone is None for user in users)
    assert all(verify_password("volunteer-secret", user.password_hash) for user in users)
    assert elder is not None and elder.name == "测试老人"
    assert elder.age is None and elder.health_info is None
    assert binding is not None
    assert binding.elder_id == elder.id
    assert binding.family_user_id == next(
        user.id for user in users if user.username == TEST_FAMILY_USERNAME
    )
    assert len(trips) == 1
    assert trips[0].elder_id == elder.id
    assert trips[0].destination == TEST_TRIP_DESTINATION
    assert trips[0].status == "active"
    assert trips[0].started_at is not None
