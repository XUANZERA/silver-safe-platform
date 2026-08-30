from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.elder import Elder
from app.models.trip import Trip

UNFINISHED_STATUSES = ("created", "active")


def get_trip_or_404(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise AppError(404, "出游任务不存在", "TRIP_NOT_FOUND")
    return trip


def get_current_trip(db: Session, elder_id: int) -> Trip | None:
    return db.scalar(
        select(Trip).where(
            Trip.elder_id == elder_id,
            Trip.status.in_(UNFINISHED_STATUSES),
        )
    )


def create_trip(db: Session, elder: Elder, destination: str) -> Trip:
    existing = db.scalar(
        select(Trip).where(
            Trip.elder_id == elder.id,
            Trip.status.in_(UNFINISHED_STATUSES),
        )
    )
    if existing is not None:
        raise AppError(409, "当前已有未完成的出游任务", "UNFINISHED_TRIP_EXISTS")

    trip = Trip(elder_id=elder.id, destination=destination.strip(), status="created")
    db.add(trip)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "当前已有未完成的出游任务", "UNFINISHED_TRIP_EXISTS") from None
    db.refresh(trip)
    return trip


def start_trip(db: Session, trip: Trip) -> Trip:
    result = db.execute(
        update(Trip)
        .where(Trip.id == trip.id, Trip.status == "created")
        .values(status="active", started_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current = get_trip_or_404(db, trip.id)
        if current.status == "active":
            raise AppError(409, "出游任务已经开始", "TRIP_ALREADY_STARTED")
        raise AppError(409, "当前状态不允许开始出游", "INVALID_TRIP_STATUS")

    db.commit()
    db.expire_all()
    return get_trip_or_404(db, trip.id)


def cancel_trip(db: Session, trip: Trip, reason: str) -> Trip:
    result = db.execute(
        update(Trip)
        .where(Trip.id == trip.id, Trip.status == "created")
        .values(
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            cancel_reason=reason.strip(),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current = get_trip_or_404(db, trip.id)
        if current.status == "active":
            raise AppError(409, "已开始的出游不能取消", "TRIP_ALREADY_STARTED")
        raise AppError(409, "已结束的出游不能取消", "TRIP_ALREADY_FINISHED")

    db.commit()
    db.expire_all()
    return get_trip_or_404(db, trip.id)


def end_trip(db: Session, trip: Trip) -> Trip:
    result = db.execute(
        update(Trip)
        .where(Trip.id == trip.id, Trip.status == "active")
        .values(status="completed", ended_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current = get_trip_or_404(db, trip.id)
        if current.status == "completed":
            raise AppError(409, "出游任务已经结束", "TRIP_ALREADY_COMPLETED")
        raise AppError(409, "出游任务尚未开始", "TRIP_NOT_ACTIVE")

    db.commit()
    db.expire_all()
    return get_trip_or_404(db, trip.id)
