# app/services/tiktok_realtime_service.py
"""
Enhanced TikTok real-time synchronization service
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import json

from app.models.tiktok_models import (
    TikTokShop, TikTokOrder, TikTokProduct, 
    TikTokVideo, TikTokVideoMetrics, WebhookEvent
)
from app.core.config import settings
from app.services.webhook_service import WebhookService
from app.external.campaign_service_client import CampaignServiceClient
from app.external.analytics_service_client import AnalyticsServiceClient

logger = logging.getLogger(__name__)


class TikTokRealtimeService:
    """Service for real-time TikTok data synchronization"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.webhook_service = WebhookService()
        self.campaign_client = CampaignServiceClient()
        self.analytics_client = AnalyticsServiceClient()
        
        # WebSocket connections for real-time updates
        self.active_connections: Dict[str, List[Any]] = {}
        
    async def register_webhooks(self, shop_id: str) -> Dict[str, Any]:
        """Register webhooks with TikTok for real-time updates"""
        webhook_endpoints = [
            {
                "event": "order.created",
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/order-created"
            },
            {
                "event": "order.updated", 
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/order-updated"
            },
            {
                "event": "product.updated",
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/product-updated"
            },
            {
                "event": "inventory.changed",
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/inventory-changed"
            },
            {
                "event": "video.posted",
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/video-posted"
            },
            {
                "event": "video.metrics.updated",
                "url": f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/tiktok/video-metrics"
            }
        ]
        
        # Register each webhook with TikTok
        registered = []
        for webhook in webhook_endpoints:
            try:
                # Call TikTok API to register webhook
                # This would use your TikTokShopClient
                logger.info(f"Registering webhook for {webhook['event']}")
                registered.append(webhook)
            except Exception as e:
                logger.error(f"Failed to register webhook {webhook['event']}: {e}")
        
        return {
            "shop_id": shop_id,
            "registered_webhooks": registered,
            "count": len(registered)
        }
    
    async def handle_order_created(self, webhook_data: Dict[str, Any]) -> None:
        """Handle real-time order creation"""
        try:
            order_data = webhook_data.get("data", {})
            shop_id = webhook_data.get("shop_id")
            
            # Create or update order in database
            order = TikTokOrder(
                id=f"order_{order_data['order_id']}",
                shop_id=shop_id,
                order_id=order_data["order_id"],
                order_status=order_data["order_status"],
                payment_status=order_data.get("payment_status"),
                total_amount=order_data.get("total_amount", 0),
                buyer_info=order_data.get("buyer_info", {}),
                line_items=order_data.get("line_items", []),
                create_time=order_data.get("create_time"),
                synced_at=datetime.utcnow()
            )
            
            self.db.add(order)
            await self.db.commit()
            
            # Check for video attribution
            await self._attribute_order_to_video(order)
            
            # Notify analytics service
            await self.analytics_client.update_campaign_metrics({
                "order_id": order.order_id,
                "shop_id": shop_id,
                "gmv": float(order.total_amount),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Send real-time update via WebSocket
            await self._broadcast_update("order_created", {
                "order_id": order.order_id,
                "shop_id": shop_id,
                "total_amount": float(order.total_amount)
            })
            
        except Exception as e:
            logger.error(f"Error handling order creation: {e}")
            await self.db.rollback()
    
    async def handle_video_metrics_update(self, webhook_data: Dict[str, Any]) -> None:
        """Handle real-time video metrics updates"""
        try:
            video_data = webhook_data.get("data", {})
            video_id = video_data.get("video_id")
            
            # Update video metrics
            stmt = update(TikTokVideo).where(
                TikTokVideo.video_id == video_id
            ).values(
                view_count=video_data.get("view_count", 0),
                like_count=video_data.get("like_count", 0),
                comment_count=video_data.get("comment_count", 0),
                share_count=video_data.get("share_count", 0),
                play_count=video_data.get("play_count", 0),
                updated_at=datetime.utcnow()
            )
            
            await self.db.execute(stmt)
            
            # Create metrics snapshot
            metrics_snapshot = TikTokVideoMetrics(
                id=f"metrics_{video_id}_{datetime.utcnow().timestamp()}",
                video_id=video_id,
                view_count=video_data.get("view_count", 0),
                like_count=video_data.get("like_count", 0),
                comment_count=video_data.get("comment_count", 0),
                share_count=video_data.get("share_count", 0),
                play_count=video_data.get("play_count", 0),
                engagement_rate=self._calculate_engagement_rate(video_data),
                view_velocity=video_data.get("view_velocity", 0),
                recorded_at=datetime.utcnow()
            )
            
            self.db.add(metrics_snapshot)
            await self.db.commit()
            
            # Check if this video is a campaign deliverable
            await self._check_deliverable_performance(video_id, video_data)
            
            # Broadcast update
            await self._broadcast_update("video_metrics", {
                "video_id": video_id,
                "metrics": video_data
            })
            
        except Exception as e:
            logger.error(f"Error handling video metrics update: {e}")
            await self.db.rollback()
    
    async def _attribute_order_to_video(self, order: TikTokOrder) -> None:
        """Attribute order to creator video using real-time data"""
        # This would implement your attribution logic
        # For example, checking recent video views before purchase
        pass
    
    async def _check_deliverable_performance(self, video_id: str, metrics: Dict[str, Any]) -> None:
        """Check if video meets deliverable requirements"""
        # Query if this video is a campaign deliverable
        video_result = await self.db.execute(
            select(TikTokVideo).where(
                TikTokVideo.video_id == video_id,
                TikTokVideo.is_deliverable == True
            )
        )
        video = video_result.scalar_one_or_none()
        
        if video and video.deliverable_id:
            # Notify campaign service about performance update
            await self.campaign_client.update_deliverable_metrics(
                deliverable_id=video.deliverable_id,
                metrics=metrics
            )
    
    def _calculate_engagement_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate engagement rate from metrics"""
        views = metrics.get("view_count", 0)
        if views == 0:
            return 0.0
        
        engagements = (
            metrics.get("like_count", 0) +
            metrics.get("comment_count", 0) +
            metrics.get("share_count", 0)
        )
        
        return (engagements / views) * 100
    
    async def _broadcast_update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast real-time updates to connected clients"""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send to all connected WebSocket clients
        for connection in self.active_connections.get(event_type, []):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")


class TikTokPollingService:
    """Service for polling TikTok API for updates"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.polling_intervals = {
            "orders": 60,  # Poll orders every minute
            "products": 300,  # Poll products every 5 minutes
            "videos": 120,  # Poll videos every 2 minutes
            "metrics": 180   # Poll video metrics every 3 minutes
        }
        self.running = False
    
    async def start_polling(self):
        """Start all polling tasks"""
        self.running = True
        
        tasks = [
            asyncio.create_task(self._poll_orders()),
            asyncio.create_task(self._poll_products()),
            asyncio.create_task(self._poll_videos()),
            asyncio.create_task(self._poll_video_metrics())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Polling service stopped")
    
    async def stop_polling(self):
        """Stop all polling tasks"""
        self.running = False
    
    async def _poll_orders(self):
        """Poll for new orders"""
        while self.running:
            try:
                shops = await self._get_active_shops()
                
                for shop in shops:
                    # Get orders created in last polling interval
                    from_time = datetime.utcnow() - timedelta(seconds=self.polling_intervals["orders"] * 2)
                    
                    # Use your TikTokShopClient to fetch recent orders
                    # Process and save new orders
                    logger.info(f"Polling orders for shop {shop.shop_id}")
                
            except Exception as e:
                logger.error(f"Error polling orders: {e}")
            
            await asyncio.sleep(self.polling_intervals["orders"])
    
    async def _poll_videos(self):
        """Poll for new videos from creators"""
        while self.running:
            try:
                # Get all active TikTok accounts
                accounts = await self._get_active_accounts()
                
                for account in accounts:
                    # Fetch recent videos
                    logger.info(f"Polling videos for account {account.username}")
                    # Process new videos
                
            except Exception as e:
                logger.error(f"Error polling videos: {e}")
            
            await asyncio.sleep(self.polling_intervals["videos"])
    
    async def _poll_video_metrics(self):
        """Poll for updated video metrics"""
        while self.running:
            try:
                # Get videos that need metric updates
                videos = await self._get_videos_for_metric_update()
                
                for video in videos:
                    logger.info(f"Updating metrics for video {video.video_id}")
                    # Fetch and update metrics
                
            except Exception as e:
                logger.error(f"Error polling video metrics: {e}")
            
            await asyncio.sleep(self.polling_intervals["metrics"])
    
    async def _poll_products(self):
        """Poll for product updates"""
        while self.running:
            try:
                shops = await self._get_active_shops()
                
                for shop in shops:
                    logger.info(f"Polling products for shop {shop.shop_id}")
                    # Fetch and update products
                
            except Exception as e:
                logger.error(f"Error polling products: {e}")
            
            await asyncio.sleep(self.polling_intervals["products"])
    
    async def _get_active_shops(self) -> List[TikTokShop]:
        """Get all active shops"""
        result = await self.db.execute(
            select(TikTokShop).where(TikTokShop.is_active == True)
        )
        return result.scalars().all()
    
    async def _get_active_accounts(self) -> List[Any]:
        """Get all active TikTok accounts"""
        from app.models.tiktok_models import TikTokAccount
        result = await self.db.execute(
            select(TikTokAccount).where(TikTokAccount.is_active == True)
        )
        return result.scalars().all()
    
    async def _get_videos_for_metric_update(self) -> List[TikTokVideo]:
        """Get videos that need metric updates"""
        # Get videos that haven't been updated in the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        result = await self.db.execute(
            select(TikTokVideo).where(
                TikTokVideo.is_deliverable == True,
                TikTokVideo.updated_at < cutoff_time
            ).limit(50)
        )
        return result.scalars().all()