from fastapi import APIRouter

from app.api.v1 import auth, capsules, health, users

api_router_v1 = APIRouter(prefix="/api/v1")
api_router_v1.include_router(health.router)
api_router_v1.include_router(auth.router)
api_router_v1.include_router(users.router)
api_router_v1.include_router(capsules.router)
