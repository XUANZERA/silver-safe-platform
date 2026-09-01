from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.elder import Elder
    from app.models.trip import Trip
    from app.models.user import User


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('emergency', 'geofence_exit')",
            name="ck_alerts_type",
        ),
        CheckConstraint(
            "status IN ('new', 'processing', 'resolved')",
            name="ck_alerts_status",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_alerts_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_alerts_longitude",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_alerts_coordinate_pair",
        ),
        CheckConstraint(
            "("
            "status = 'new' AND handler_id IS NULL AND accepted_at IS NULL "
            "AND resolution IS NULL AND resolved_at IS NULL"
            ") OR ("
            "status = 'processing' AND handler_id IS NOT NULL "
            "AND accepted_at IS NOT NULL AND resolution IS NULL "
            "AND resolved_at IS NULL"
            ") OR ("
            "status = 'resolved' AND handler_id IS NOT NULL "
            "AND accepted_at IS NOT NULL AND resolution IS NOT NULL "
            "AND resolved_at IS NOT NULL"
            ")",
            name="ck_alerts_state_fields",
        ),
        Index("ix_alerts_occurred", "occurred_at"),
        Index("ix_alerts_status_occurred", "status", "occurred_at"),
        Index("ix_alerts_status_type_occurred", "status", "type", "occurred_at"),
        Index("ix_alerts_elder_status_occurred", "elder_id", "status", "occurred_at"),
        Index("ix_alerts_trip_type_status", "trip_id", "type", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"))
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="new")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    handler_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    elder: Mapped["Elder"] = relationship(back_populates="alerts")
    trip: Mapped["Trip"] = relationship(back_populates="alerts")
    handler: Mapped["User | None"] = relationship(foreign_keys=[handler_id])
    logs: Mapped[list["AlertLog"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="AlertLog.created_at",
    )


class AlertLog(Base):
    __tablename__ = "alert_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('accepted', 'resolved')",
            name="ck_alert_logs_action",
        ),
        Index("ix_alert_logs_alert_created", "alert_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    alert: Mapped["Alert"] = relationship(back_populates="logs")
    operator: Mapped["User"] = relationship(foreign_keys=[operator_id])
