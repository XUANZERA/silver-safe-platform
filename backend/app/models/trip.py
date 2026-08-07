from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.elder import Elder
    from app.models.location import Location


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'active', 'completed', 'cancelled')",
            name="ck_trips_status",
        ),
        CheckConstraint(
            "("
            "status = 'created' AND started_at IS NULL AND ended_at IS NULL "
            "AND cancelled_at IS NULL AND cancel_reason IS NULL"
            ") OR ("
            "status = 'active' AND started_at IS NOT NULL AND ended_at IS NULL "
            "AND cancelled_at IS NULL AND cancel_reason IS NULL"
            ") OR ("
            "status = 'completed' AND started_at IS NOT NULL AND ended_at IS NOT NULL "
            "AND cancelled_at IS NULL AND cancel_reason IS NULL"
            ") OR ("
            "status = 'cancelled' AND started_at IS NULL AND ended_at IS NULL "
            "AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL"
            ")",
            name="ck_trips_state_fields",
        ),
        Index(
            "uq_trips_elder_unfinished",
            "elder_id",
            unique=True,
            sqlite_where=text("status IN ('created', 'active')"),
            postgresql_where=text("status IN ('created', 'active')"),
        ),
        Index("ix_trips_elder_status", "elder_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"))
    destination: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="created")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    elder: Mapped["Elder"] = relationship(back_populates="trips")
    locations: Mapped[list["Location"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="trip")
