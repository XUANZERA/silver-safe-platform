from sqlalchemy.orm import Session

from app.core.field_encryption import decrypt_health_info
from app.models.elder import Elder
from app.models.user import User
from app.schemas.elder import ElderResponse
from app.services.audit import add_audit_log


def elder_to_response(
    db: Session,
    *,
    elder: Elder,
    viewer: User,
    ip_address: str | None,
) -> ElderResponse:
    can_read_health_info = viewer.role in {"elder", "family"}
    health_info = decrypt_health_info(elder.health_info) if can_read_health_info else None
    if elder.health_info is not None:
        add_audit_log(
            db,
            action="health_info.read",
            outcome="success" if can_read_health_info else "redacted",
            actor_user_id=viewer.id,
            resource_type="elder",
            resource_id=elder.id,
            ip_address=ip_address,
            details={"viewer_role": viewer.role},
        )
    return ElderResponse(
        id=elder.id,
        user_id=elder.user_id,
        name=elder.name,
        age=elder.age,
        health_info=health_info,
    )
