# app/tasks/tiktok_sync_tasks.py
"""
Celery tasks for continuous TikTok data synchronization
"""

from celery import shared_task
from celery.schedules import crontab
from datetime import datetime, timedelta
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_tiktok_orders(self, shop_id: str = None):
    """Sync TikTok orders - runs every minute"""
    try:
        from app.services.order_service import OrderService
        from app.models.database import SessionLocal
        
        db = SessionLocal()
        order_service = OrderService(db)
        
        # If no shop_id provided, sync all active shops
        if not shop_id:
            shops = db.query(TikTokShop).filter(TikTokShop.is_active == True).all()
            shop_ids = [shop.shop_id for shop in shops]
        else:
            shop_ids = [shop_id]
        
        total_synced = 0
        
        for sid in shop_ids:
            try:
                # Sync orders from last 5 minutes
                synced = asyncio.run(
                    order_service.sync_recent_orders(sid, minutes=5)
                )
                total_synced += synced
                logger.info(f"Synced {synced} orders for shop {sid}")
            except Exception as e:
                logger.error(f"Failed to sync orders for shop {sid}: {e}")
        
        db.close()
        return f"Synced {total_synced} orders across {len(shop_ids)} shops"
        
    except Exception as e:
        logger.error(f"Order sync task failed: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3)
def sync_video_metrics(self, creator_id: str = None):
    """Sync video metrics - runs every 3 minutes"""
    try:
        from app.services.tiktok_video_service import TikTokVideoService
        from app.models.database import AsyncSessionLocal
        
        async def _sync():
            async with AsyncSessionLocal() as db:
                video_service = TikTokVideoService(db)
                
                if creator_id:
                    result = await video_service.sync_creator_videos(creator_id)
                else:
                    # Sync all active creators
                    creators = await _get_active_creators(db)
                    
                    for creator in creators:
                        try:
                            result = await video_service.sync_creator_videos(
                                creator.user_id
                            )
                            logger.info(f"Synced videos for creator {creator.username}")
                        except Exception as e:
                            logger.error(f"Failed to sync videos for {creator.username}: {e}")
        
        asyncio.run(_sync())
        return "Video metrics sync completed"
        
    except Exception as e:
        logger.error(f"Video sync task failed: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3)
def calculate_gmv_attribution(self):
    """Calculate GMV attribution - runs every hour"""
    try:
        from app.services.tiktok_video_service import TikTokVideoService
        from app.models.database import AsyncSessionLocal
        
        async def _calculate():
            async with AsyncSessionLocal() as db:
                video_service = TikTokVideoService(db)
                
                # Get all creators with recent orders
                creators = await _get_creators_with_recent_orders(db)
                
                total_attributed = 0
                
                for creator_id in creators:
                    try:
                        result = await video_service.calculate_gmv_attribution(
                            creator_id
                        )
                        if result["success"]:
                            total_attributed += result["total_attributed_orders"]
                    except Exception as e:
                        logger.error(f"Attribution failed for creator {creator_id}: {e}")
                
                return total_attributed
        
        attributed = asyncio.run(_calculate())
        return f"Attributed {attributed} orders to videos"
        
    except Exception as e:
        logger.error(f"GMV attribution task failed: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True)
def check_deliverable_deadlines(self):
    """Check for approaching deliverable deadlines - runs every hour"""
    try:
        from app.external.campaign_service_client import CampaignServiceClient
        from app.external.notification_service_client import NotificationServiceClient
        
        campaign_client = CampaignServiceClient()
        notification_client = NotificationServiceClient()
        
        async def _check_deadlines():
            # Get deliverables due in next 24 hours
            upcoming = await campaign_client.get_upcoming_deliverables(hours=24)
            
            for deliverable in upcoming:
                # Send reminder notification
                await notification_client.send_deliverable_reminder(
                    creator_id=deliverable["creator_id"],
                    campaign_name=deliverable["campaign_name"],
                    due_date=deliverable["due_date"]
                )
        
        asyncio.run(_check_deadlines())
        return "Deadline check completed"
        
    except Exception as e:
        logger.error(f"Deadline check task failed: {e}")


@shared_task(bind=True)
def sync_product_inventory(self):
    """Sync product inventory - runs every 5 minutes"""
    try:
        from app.services.product_service import ProductService
        from app.models.database import SessionLocal
        
        db = SessionLocal()
        product_service = ProductService(db)
        
        shops = db.query(TikTokShop).filter(TikTokShop.is_active == True).all()
        
        for shop in shops:
            try:
                # Sync inventory for products with low stock
                asyncio.run(
                    product_service.sync_low_stock_products(shop.shop_id)
                )
            except Exception as e:
                logger.error(f"Inventory sync failed for shop {shop.shop_id}: {e}")
        
        db.close()
        return "Inventory sync completed"
        
    except Exception as e:
        logger.error(f"Inventory sync task failed: {e}")


# Helper functions
async def _get_active_creators(db):
    """Get all active creators"""
    from sqlalchemy import select
    from app.models.tiktok_models import TikTokAccount
    
    result = await db.execute(
        select(TikTokAccount).where(TikTokAccount.is_active == True)
    )
    return result.scalars().all()


async def _get_creators_with_recent_orders(db):
    """Get creator IDs with orders in last hour"""
    from sqlalchemy import select, distinct
    from app.models.tiktok_models import TikTokOrder
    
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    result = await db.execute(
        select(distinct(TikTokOrder.creator_id))
        .where(
            TikTokOrder.synced_at >= one_hour_ago,
            TikTokOrder.creator_id.isnot(None)
        )
    )
    return result.scalars().all()


# Celery Beat Schedule
from app.tasks.celery_app import celery_app

celery_app.conf.beat_schedule.update({
    'sync-tiktok-orders': {
        'task': 'app.tasks.tiktok_sync_tasks.sync_tiktok_orders',
        'schedule': 60.0,  # Every minute
    },
    'sync-video-metrics': {
        'task': 'app.tasks.tiktok_sync_tasks.sync_video_metrics',
        'schedule': 180.0,  # Every 3 minutes
    },
    'calculate-gmv-attribution': {
        'task': 'app.tasks.tiktok_sync_tasks.calculate_gmv_attribution',
        'schedule': crontab(minute=0),  # Every hour
    },
    'check-deliverable-deadlines': {
        'task': 'app.tasks.tiktok_sync_tasks.check_deliverable_deadlines',
        'schedule': crontab(minute=0),  # Every hour
    },
    'sync-product-inventory': {
        'task': 'app.tasks.tiktok_sync_tasks.sync_product_inventory',
        'schedule': 300.0,  # Every 5 minutes
    },
})