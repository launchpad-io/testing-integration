from fastapi import APIRouter
from .endpoints import auth, products, orders, shops, webhooks, tiktok_account
from .endpoints import tiktok_video

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(shops.router, prefix="/shops", tags=["shops"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(tiktok_account.router, prefix="/integrations/tiktok", tags=["tiktok-integration"])
api_router.include_router(tiktok_video.router, prefix="/integrations/tiktok", tags=["tiktok-video"])


