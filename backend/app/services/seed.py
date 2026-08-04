from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.field_encryption import encrypt_health_info
from app.core.security import hash_password
from app.models.elder import Elder, ElderFamilyBinding
from app.models.geofence import Geofence
from app.models.user import User

DEMO_PASSWORD = "demo123"


def _get_or_create_user(
    session: Session,
    *,
    username: str,
    role: str,
    phone: str,
) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is not None:
        return user

    user = User(
        username=username,
        password_hash=hash_password(DEMO_PASSWORD),
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
        role="elder",
        phone="13800000001",
    )
    family_user = _get_or_create_user(
        session,
        username="family01",
        role="family",
        phone="13800000002",
    )
    _get_or_create_user(
        session,
        username="operator01",
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

    geofence = session.scalar(select(Geofence).where(Geofence.elder_id == elder.id))
    if geofence is None:
        session.add(
            Geofence(
                elder_id=elder.id,
                center_latitude=31.230391,
                center_longitude=121.473701,
                radius_meters=500,
                enabled=True,
            )
        )
    session.commit()
