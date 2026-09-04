from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.elder import Elder


class Geofence(Base):
    __tablename__ = "geofences"
    __table_args__ = (
        CheckConstraint("center_latitude BETWEEN -90 AND 90", name="ck_geofences_latitude"),
        CheckConstraint("center_longitude BETWEEN -180 AND 180", name="ck_geofences_longitude"),
        CheckConstraint("radius_meters > 0", name="ck_geofences_radius"),
        CheckConstraint("enabled IN (0, 1)", name="ck_geofences_enabled"),
        CheckConstraint("crs IS NULL OR crs = 'WGS84'", name="ck_geofences_crs"),
    )

    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), primary_key=True)
    center_latitude: Mapped[float] = mapped_column(Float)
    center_longitude: Mapped[float] = mapped_column(Float)
    radius_meters: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(default=True)
    crs: Mapped[str | None] = mapped_column(String(20), nullable=True)

    elder: Mapped["Elder"] = relationship(back_populates="geofence")
