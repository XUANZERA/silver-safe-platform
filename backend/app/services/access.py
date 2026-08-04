from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.elder import Elder, ElderFamilyBinding
from app.models.user import User


def ensure_elder_access(db: Session, user: User, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if elder is None:
        raise AppError(404, "老人不存在", "ELDER_NOT_FOUND")

    if user.role == "operator" or elder.user_id == user.id:
        return elder

    if user.role == "family":
        binding = db.scalar(
            select(ElderFamilyBinding.elder_id).where(
                ElderFamilyBinding.elder_id == elder_id,
                ElderFamilyBinding.family_user_id == user.id,
            )
        )
        if binding is not None:
            return elder

    raise AppError(404, "老人不存在或不可访问", "ELDER_NOT_FOUND")


def list_accessible_elders(db: Session, user: User) -> list[Elder]:
    query = select(Elder).order_by(Elder.id)
    if user.role == "elder":
        query = query.where(Elder.user_id == user.id)
    elif user.role == "family":
        query = query.join(ElderFamilyBinding).where(ElderFamilyBinding.family_user_id == user.id)
    elif user.role != "operator":
        return []
    return list(db.scalars(query).all())
