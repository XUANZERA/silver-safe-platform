from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
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
    _get_or_create_user(
        session,
        username="elder01",
        role="elder",
        phone="13800000001",
    )
    _get_or_create_user(
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
    session.commit()
