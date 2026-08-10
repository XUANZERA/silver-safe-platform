from fastapi import APIRouter

from app.api.routes import alerts, auth, elders, health, locations, trips

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(elders.router, tags=["elders"])
api_router.include_router(trips.router, tags=["trips"])
api_router.include_router(locations.router, tags=["locations"])
api_router.include_router(alerts.router, tags=["alerts"])
