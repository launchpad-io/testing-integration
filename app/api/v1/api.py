from fastapi import APIRouter

from app.api.v1.endpoints import tiktok_video, tiktok_account

api_router = APIRouter()

# Include TikTok video endpoints
api_router.include_router(
    tiktok_video.router,
    prefix="/tiktok",
    tags=["TikTok Video Integration"]
)

# Include TikTok account endpoints
api_router.include_router(
    tiktok_account.router,
    prefix="/tiktok/account",
    tags=["TikTok Account Authentication"]
) 