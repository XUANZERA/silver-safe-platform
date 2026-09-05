import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import Settings
from app.core.security import verify_password
from app.db.base import Base
from app.models.elder import Elder, ElderFamilyBinding
from app.models.geofence import Geofence
from app.models.trip import Trip
from app.models.user import User
from app.services.seed import (
    TEST_ELDER_USERNAME,
    TEST_FAMILY_USERNAME,
    TEST_GEOFENCE_LATITUDE,
    TEST_GEOFENCE_LONGITUDE,
    TEST_GEOFENCE_RADIUS_METERS,
    TEST_TRIP_DESTINATION,
    VOLUNTEER_TEST_ACCOUNT_COUNT,
    seed_environment_data,
    volunteer_test_username,
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


def test_testing_seed_creates_ten_isolated_groups_with_geofences_and_active_trips() -> None:
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
        elders = session.scalars(select(Elder).order_by(Elder.id)).all()
        bindings = session.scalars(select(ElderFamilyBinding)).all()
        geofences = session.scalars(select(Geofence).order_by(Geofence.elder_id)).all()
        trips = session.scalars(select(Trip).order_by(Trip.elder_id)).all()

    expected_users = sorted(
        [
            (volunteer_test_username(role, group_number), role)
            for group_number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1)
            for role in ("elder", "family")
        ]
    )
    assert [(user.username, user.role) for user in users] == expected_users
    assert volunteer_test_username("elder", 1) == TEST_ELDER_USERNAME
    assert volunteer_test_username("family", 1) == TEST_FAMILY_USERNAME
    assert TEST_TRIP_DESTINATION == "测试公园01"
    assert all(user.phone is None for user in users)
    assert all(verify_password("volunteer-secret", user.password_hash) for user in users)
    assert len(elders) == VOLUNTEER_TEST_ACCOUNT_COUNT
    assert all(elder.age is None and elder.health_info is None for elder in elders)
    assert [elder.name for elder in elders] == [
        f"测试老人{group_number:02d}" for group_number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1)
    ]

    users_by_name = {user.username: user for user in users}
    elders_by_user_id = {elder.user_id: elder for elder in elders}
    assert len(bindings) == VOLUNTEER_TEST_ACCOUNT_COUNT
    for group_number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1):
        elder_user = users_by_name[volunteer_test_username("elder", group_number)]
        family_user = users_by_name[volunteer_test_username("family", group_number)]
        elder = elders_by_user_id[elder_user.id]
        assert [(item.elder_id, item.family_user_id) for item in bindings].count(
            (elder.id, family_user.id)
        ) == 1

    assert len(geofences) == VOLUNTEER_TEST_ACCOUNT_COUNT
    assert all(geofence.enabled is True for geofence in geofences)
    assert all(geofence.crs == "WGS84" for geofence in geofences)
    assert all(geofence.center_latitude == TEST_GEOFENCE_LATITUDE for geofence in geofences)
    assert all(geofence.center_longitude == TEST_GEOFENCE_LONGITUDE for geofence in geofences)
    assert all(geofence.radius_meters == TEST_GEOFENCE_RADIUS_METERS for geofence in geofences)

    assert len(trips) == VOLUNTEER_TEST_ACCOUNT_COUNT
    assert [trip.destination for trip in trips] == [
        f"测试公园{group_number:02d}" for group_number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1)
    ]
    assert all(trip.status == "active" for trip in trips)
    assert all(trip.started_at is not None for trip in trips)
