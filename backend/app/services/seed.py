from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.coordinates import CoordinateReferenceSystem
from app.core.field_encryption import encrypt_health_info
from app.core.security import hash_password
from app.models.elder import Elder, ElderFamilyBinding
from app.models.geofence import Geofence
from app.models.trip import Trip
from app.models.types import utc_now
from app.models.user import User
from app.services.trips import get_current_trip

DEMO_PASSWORD = "demo123"
VOLUNTEER_TEST_ACCOUNT_COUNT = 10
TEST_ELDER_USERNAME = "elder_test_01"
TEST_FAMILY_USERNAME = "family_test_01"
TEST_TRIP_DESTINATION = "测试公园01"
TEST_GEOFENCE_LATITUDE = 23.119990
TEST_GEOFENCE_LONGITUDE = 113.324520
TEST_GEOFENCE_RADIUS_METERS = 500


def volunteer_test_username(role: str, group_number: int) -> str:
    if role not in {"elder", "family"}:
        raise ValueError(f"不支持的志愿者测试账号角色：{role}")
    if not 1 <= group_number <= VOLUNTEER_TEST_ACCOUNT_COUNT:
        raise ValueError(f"志愿者测试账号组号超出范围：{group_number}")
    return f"{role}_test_{group_number:02d}"


def _get_or_create_user(
    session: Session,
    *,
    username: str,
    password: str,
    role: str,
    phone: str | None,
) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is not None:
        return user

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        phone=phone,
    )
    session.add(user)
    session.flush()
    return user


def seed_demo_data(session: Session) -> None:
    elder_user = _get_or_create_user(
        session,
        username="elder01",
        password=DEMO_PASSWORD,
        role="elder",
        phone="13800000001",
    )
    family_user = _get_or_create_user(
        session,
        username="family01",
        password=DEMO_PASSWORD,
        role="family",
        phone="13800000002",
    )
    _get_or_create_user(
        session,
        username="operator01",
        password=DEMO_PASSWORD,
        role="operator",
        phone="13800000003",
    )

    elder = session.scalar(select(Elder).where(Elder.user_id == elder_user.id))
    if elder is None:
        elder = Elder(
            user_id=elder_user.id,
            name="王奶奶",
            age=68,
            health_info=encrypt_health_info("轻度高血压"),
        )
        session.add(elder)
        session.flush()
    elif elder.health_info is not None:
        elder.health_info = encrypt_health_info(elder.health_info)

    binding = session.scalar(
        select(ElderFamilyBinding).where(
            ElderFamilyBinding.elder_id == elder.id,
            ElderFamilyBinding.family_user_id == family_user.id,
        )
    )
    if binding is None:
        session.add(ElderFamilyBinding(elder_id=elder.id, family_user_id=family_user.id))

    session.commit()


def seed_volunteer_test_data(session: Session, *, password: str) -> None:
    for group_number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1):
        suffix = f"{group_number:02d}"
        elder_user = _get_or_create_user(
            session,
            username=volunteer_test_username("elder", group_number),
            password=password,
            role="elder",
            phone=None,
        )
        family_user = _get_or_create_user(
            session,
            username=volunteer_test_username("family", group_number),
            password=password,
            role="family",
            phone=None,
        )

        elder = session.scalar(select(Elder).where(Elder.user_id == elder_user.id))
        if elder is None:
            elder = Elder(
                user_id=elder_user.id,
                name=f"测试老人{suffix}",
                age=None,
                health_info=None,
            )
            session.add(elder)
            session.flush()

        binding = session.scalar(
            select(ElderFamilyBinding).where(
                ElderFamilyBinding.elder_id == elder.id,
                ElderFamilyBinding.family_user_id == family_user.id,
            )
        )
        if binding is None:
            session.add(
                ElderFamilyBinding(
                    elder_id=elder.id,
                    family_user_id=family_user.id,
                )
            )

        geofence = session.get(Geofence, elder.id)
        if geofence is None:
            session.add(
                Geofence(
                    elder_id=elder.id,
                    center_latitude=TEST_GEOFENCE_LATITUDE,
                    center_longitude=TEST_GEOFENCE_LONGITUDE,
                    radius_meters=TEST_GEOFENCE_RADIUS_METERS,
                    enabled=True,
                    crs=CoordinateReferenceSystem.WGS84.value,
                )
            )

        trip: Trip | None = get_current_trip(session, elder.id)
        if trip is None:
            session.add(
                Trip(
                    elder_id=elder.id,
                    destination=f"测试公园{suffix}",
                    status="active",
                    started_at=utc_now(),
                )
            )
        elif trip.status == "created":
            trip.status = "active"
            trip.started_at = utc_now()

    session.commit()


def seed_environment_data(
    session: Session,
    *,
    app_env: str,
    test_account_password: str | None = None,
) -> None:
    environment = app_env.lower()
    if environment == "development":
        seed_demo_data(session)
    elif environment == "testing":
        if not test_account_password:
            raise ValueError("测试环境缺少 TEST_ACCOUNT_PASSWORD")
        seed_volunteer_test_data(session, password=test_account_password)
