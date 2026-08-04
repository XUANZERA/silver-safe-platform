from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.elder import Elder, ElderFamilyBinding


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('elder', 'family', 'operator')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    elder: Mapped["Elder | None"] = relationship(back_populates="user", uselist=False)
    family_bindings: Mapped[list["ElderFamilyBinding"]] = relationship(
        back_populates="family_user",
        foreign_keys="ElderFamilyBinding.family_user_id",
    )
