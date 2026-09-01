from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.alert import Alert, AlertLog
from app.models.elder import Elder, ElderFamilyBinding
from app.models.user import User
from app.schemas.alert import (
    AlertDetailResponse,
    AlertLogResponse,
    AlertResponse,
    UserSummary,
)

ALERT_LOAD_OPTIONS = (joinedload(Alert.handler),)


def get_alert_or_404(db: Session, alert_id: int, *, include_logs: bool = False) -> Alert:
    options = list(ALERT_LOAD_OPTIONS)
    if include_logs:
        options.append(selectinload(Alert.logs).joinedload(AlertLog.operator))
    alert = db.scalar(select(Alert).options(*options).where(Alert.id == alert_id))
    if alert is None:
        raise AppError(404, "告警事件不存在", "ALERT_NOT_FOUND")
    return alert


def get_accessible_alert_or_404(
    db: Session,
    *,
    alert_id: int,
    viewer: User,
    include_logs: bool = False,
) -> Alert:
    query = select(Alert)
    if viewer.role == "elder":
        query = query.join(Elder).where(Elder.user_id == viewer.id)
    elif viewer.role == "family":
        query = (
            query.join(Elder)
            .join(ElderFamilyBinding)
            .where(ElderFamilyBinding.family_user_id == viewer.id)
        )
    elif viewer.role != "operator":
        raise AppError(404, "告警事件不存在", "ALERT_NOT_FOUND")

    options = list(ALERT_LOAD_OPTIONS)
    if include_logs:
        options.append(selectinload(Alert.logs).joinedload(AlertLog.operator))
    alert = db.scalar(query.options(*options).where(Alert.id == alert_id))
    if alert is None:
        raise AppError(404, "告警事件不存在", "ALERT_NOT_FOUND")
    return alert


def alert_to_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        elder_id=alert.elder_id,
        trip_id=alert.trip_id,
        type=alert.type,
        status=alert.status,
        latitude=alert.latitude,
        longitude=alert.longitude,
        occurred_at=alert.occurred_at,
        handler=(
            UserSummary(id=alert.handler.id, username=alert.handler.username)
            if alert.handler
            else None
        ),
        accepted_at=alert.accepted_at,
        resolved_at=alert.resolved_at,
        resolution=alert.resolution,
    )


def alert_detail_to_response(alert: Alert) -> AlertDetailResponse:
    return AlertDetailResponse(
        alert=alert_to_response(alert),
        logs=[
            AlertLogResponse(
                id=log.id,
                action=log.action,
                operator=UserSummary(
                    id=log.operator.id,
                    username=log.operator.username,
                ),
                created_at=log.created_at,
            )
            for log in alert.logs
        ],
    )


def create_or_get_sos(
    db: Session,
    *,
    elder: Elder,
    trip_id: int,
    latitude: float | None,
    longitude: float | None,
) -> tuple[Alert, bool]:
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().sos_duplicate_seconds)
    existing = db.scalar(
        select(Alert)
        .options(*ALERT_LOAD_OPTIONS)
        .where(
            Alert.trip_id == trip_id,
            Alert.type == "emergency",
            Alert.occurred_at >= cutoff,
        )
        .order_by(Alert.occurred_at.desc(), Alert.id.desc())
        .limit(1)
    )
    if existing is not None:
        return existing, False

    alert = Alert(
        elder_id=elder.id,
        trip_id=trip_id,
        type="emergency",
        status="new",
        latitude=latitude,
        longitude=longitude,
        occurred_at=datetime.now(UTC),
    )
    db.add(alert)
    db.flush()
    return get_alert_or_404(db, alert.id), True


def accept_alert(db: Session, alert: Alert, operator: User) -> tuple[Alert, bool]:
    now = datetime.now(UTC)
    result = db.execute(
        update(Alert)
        .where(Alert.id == alert.id, Alert.status == "new")
        .values(status="processing", handler_id=operator.id, accepted_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current = get_alert_or_404(db, alert.id)
        if current.status == "processing" and current.handler_id == operator.id:
            return current, False
        if current.status == "processing":
            raise AppError(409, "告警事件已被其他运营人员接单", "ALERT_ALREADY_ACCEPTED")
        raise AppError(409, "已完成的事件不能再次接单", "ALERT_ALREADY_RESOLVED")

    db.add(AlertLog(alert_id=alert.id, operator_id=operator.id, action="accepted"))
    db.commit()
    db.expire_all()
    return get_alert_or_404(db, alert.id), True


def resolve_alert(
    db: Session,
    alert: Alert,
    operator: User,
    resolution: str,
) -> tuple[Alert, bool]:
    now = datetime.now(UTC)
    clean_resolution = resolution.strip()
    result = db.execute(
        update(Alert)
        .where(
            Alert.id == alert.id,
            Alert.status == "processing",
            Alert.handler_id == operator.id,
        )
        .values(status="resolved", resolution=clean_resolution, resolved_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current = get_alert_or_404(db, alert.id)
        if (
            current.status == "resolved"
            and current.handler_id == operator.id
            and current.resolution == clean_resolution
        ):
            return current, False
        if current.status == "new":
            raise AppError(409, "请先接单再完成处置", "ALERT_NOT_ACCEPTED")
        if current.status == "resolved":
            raise AppError(409, "告警事件已经完成", "ALERT_ALREADY_RESOLVED")
        raise AppError(403, "只能完成自己接单的事件", "ALERT_HANDLER_MISMATCH")

    db.add(AlertLog(alert_id=alert.id, operator_id=operator.id, action="resolved"))
    db.commit()
    db.expire_all()
    return get_alert_or_404(db, alert.id), True
