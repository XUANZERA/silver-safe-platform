from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.geofence import Geofence
from app.schemas.common import ApiResponse
from app.schemas.elder import ElderListResponse, ElderResponse, GeofenceResponse
from app.services.access import ensure_elder_access, list_accessible_elders
from app.services.audit import client_ip
from app.services.privacy import elder_to_response

router = APIRouter()


@router.get("/elders", response_model=ApiResponse[ElderListResponse])
def list_elders(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ElderListResponse]:
    elders = list_accessible_elders(db, current_user)
    ip_address = client_ip(request)
    items = [
        elder_to_response(db, elder=elder, viewer=current_user, ip_address=ip_address)
        for elder in elders
    ]
    db.commit()
    return ApiResponse(data=ElderListResponse(items=items, total=len(items)))


@router.get("/elders/{elder_id}", response_model=ApiResponse[ElderResponse])
def get_elder(
    elder_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ElderResponse]:
    elder = ensure_elder_access(db, current_user, elder_id)
    response = elder_to_response(
        db,
        elder=elder,
        viewer=current_user,
        ip_address=client_ip(request),
    )
    db.commit()
    return ApiResponse(data=response)


@router.get("/elders/{elder_id}/geofence", response_model=ApiResponse[GeofenceResponse])
def get_geofence(
    elder_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[GeofenceResponse]:
    ensure_elder_access(db, current_user, elder_id)
    geofence = db.scalar(select(Geofence).where(Geofence.elder_id == elder_id))
    if geofence is None:
        return ApiResponse(data=None, message="暂未配置安全围栏")
    return ApiResponse(data=GeofenceResponse.model_validate(geofence))
