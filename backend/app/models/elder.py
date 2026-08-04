from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.geofence import Geofence
    from app.models.user import User


class Elder(Base):
    __tablename__ = "elders"
    __table_args__ = (
        CheckConstraint("age IS NULL OR age BETWEEN 0 AND 130", name="ck_elders_age"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int | None] = mapped_column(nullable=True)
    health_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="elder")
    family_bindings: Mapped[list["ElderFamilyBinding"]] = relationship(
        back_populates="elder",
        cascade="all, delete-orphan",
    )
    geofence: Mapped["Geofence | None"] = relationship(
        back_populates="elder",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ElderFamilyBinding(Base):
    __tablename__ = "elder_family_bindings"
    __table_args__ = (
        CheckConstraint("elder_id > 0", name="ck_bindings_elder_id"),
        CheckConstraint("family_user_id > 0", name="ck_bindings_family_user_id"),
    )

    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), primary_key=True)
    family_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, index=True
    )

    elder: Mapped["Elder"] = relationship(back_populates="family_bindings")
    family_user: Mapped["User"] = relationship(
        back_populates="family_bindings",
        foreign_keys=[family_user_id],
    )
