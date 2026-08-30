from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.trip import Trip


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_locations_latitude"),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_locations_longitude",
        ),
        CheckConstraint(
            "speed_mps IS NULL OR speed_mps BETWEEN 0 AND 100",
            name="ck_locations_speed",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters BETWEEN 0 AND 10000",
            name="ck_locations_accuracy",
        ),
        CheckConstraint(
            "source IN ('simulation', 'h5')",
            name="ck_locations_source",
        ),
        UniqueConstraint(
            "trip_id",
            "client_location_id",
            name="uq_locations_trip_client_location",
        ),
        Index("ix_locations_trip_recorded", "trip_id", "recorded_at"),
        Index("ix_locations_trip_received", "trip_id", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    client_location_id: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="h5")
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime())
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    trip: Mapped["Trip"] = relationship(back_populates="locations")
