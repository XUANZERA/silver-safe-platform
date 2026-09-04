from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.coordinates import CoordinateReferenceSystem
from app.core.errors import AppError
from app.models.alert import Alert
from app.models.location import Location
from app.models.trip import Trip
from app.models.user import User
from app.services.access import get_owned_elder
from app.services.alerts import create_or_get_sos
from app.services.audit import add_audit_log, begin_sos_audit


def _record_sos_failure(
    db: Session,
    *,
    current_user: User,
    ip_address: str | None,
    error_code: str,
) -> None:
    db.rollback()
    add_audit_log(
        db,
        action="sos.request",
        outcome="failure",
        actor_user_id=current_user.id,
        ip_address=ip_address,
        details={"error_code": error_code},
    )
    db.commit()


def request_sos(
    db: Session,
    *,
    current_user: User,
    trip_id: int,
    ip_address: str | None,
) -> tuple[Alert, bool]:
    # Serialize all SOS attempts for one authenticated account across app instances.
    # This also rate-limits authenticated non-elder misuse before role validation.
    db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(id=User.id)
        .execution_options(synchronize_session=False)
    )
    audit_log = begin_sos_audit(
        db,
        actor_user_id=current_user.id,
        ip_address=ip_address,
    )

    try:
        elder = get_owned_elder(db, current_user)
        trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.elder_id == elder.id))
        if trip is None:
            raise AppError(404, "出游任务不存在", "TRIP_NOT_FOUND")
        if trip.status != "active":
            raise AppError(409, "当前没有进行中的出游任务", "NO_ACTIVE_TRIP")

        latest = db.scalar(
            select(Location)
            .where(
                Location.trip_id == trip.id,
                Location.source_crs == CoordinateReferenceSystem.WGS84.value,
            )
            .order_by(Location.recorded_at.desc(), Location.id.desc())
            .limit(1)
        )
        alert, created = create_or_get_sos(
            db,
            elder=elder,
            trip_id=trip.id,
            latitude=latest.latitude if latest else None,
            longitude=latest.longitude if latest else None,
        )
        audit_log.outcome = "created" if created else "deduplicated"
        audit_log.resource_type = "alert"
        audit_log.resource_id = str(alert.id)
        db.commit()
        return alert, created
    except AppError as exc:
        _record_sos_failure(
            db,
            current_user=current_user,
            ip_address=ip_address,
            error_code=exc.error_code,
        )
        raise
