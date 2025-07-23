
# app/utils/token_refresh_scheduler.py
import asyncio
from datetime import datetime, timedelta
# Use async session for non-blocking DB access
from app.models.database import AsyncSessionLocal
from app.models.tiktok_models import TikTokShop
from app.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)

class TokenRefreshScheduler:
    """Background task to refresh expiring tokens"""
    
    def __init__(self):
        self.check_interval = 3600  # Check every hour
        self.refresh_threshold = 7200  # Refresh if expires in 2 hours
    
    async def start(self):
        """Start the token refresh scheduler"""
        logger.info("Token refresh scheduler started")
        
        while True:
            try:
                await self.refresh_expiring_tokens()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Token refresh scheduler stopped")
                break
            except Exception as e:
                logger.error(f"Error in token refresh scheduler: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def refresh_expiring_tokens(self):
        """Check and refresh tokens that are about to expire (fully async)."""

        async with AsyncSessionLocal() as db:
            try:
                from sqlalchemy import select

                # Get active shops with tokens
                result = await db.execute(
                    select(TikTokShop).where(
                        TikTokShop.is_active == True,
                        TikTokShop.access_token.isnot(None)
                    )
                )
                shops = result.scalars().all()

                refreshed_count = 0

                auth_service = AuthService(db)  # AuthService can work with AsyncSession

                for shop in shops:
                    try:
                        if shop.token_updated_at and shop.access_token_expire_in:
                            expiry_time = shop.token_updated_at + timedelta(seconds=shop.access_token_expire_in)

                            # If token expires within threshold, refresh
                            if expiry_time - datetime.utcnow() < timedelta(seconds=self.refresh_threshold):
                                logger.info(f"Refreshing token for shop {shop.shop_id}")
                                await auth_service.refresh_shop_token(shop.shop_id)
                                refreshed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to refresh token for shop {shop.shop_id}: {e}")

                if refreshed_count:
                    logger.info(f"Refreshed {refreshed_count} tokens")

                await db.commit()
            except Exception as e:
                logger.error(f"Error during token refresh cycle: {e}")
