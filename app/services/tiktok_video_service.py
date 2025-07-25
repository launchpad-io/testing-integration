from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import httpx
import logging

from app.models.tiktok_models import (
    TikTokVideo, TikTokVideoMetrics, CampaignVideoDeliverable, 
    TikTokOrder, TikTokCreatorAuth, AttributionMethod, VideoStatus, DeliverableStatus
)

logger = logging.getLogger(__name__)

class TikTokVideoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tiktok_api_base = "https://open-api.tiktok.com"

    async def sync_creator_videos(self, creator_id: str, force_sync: bool = False) -> Dict[str, Any]:
        """Sync TikTok videos for a creator from TikTok API"""
        try:
            # Get creator's auth info
            auth_query = select(TikTokCreatorAuth).where(TikTokCreatorAuth.creator_id == creator_id)
            auth_result = await self.db.execute(auth_query)
            auth = auth_result.scalar_one_or_none()
            
            if not auth or not auth.is_active:
                return {"success": False, "error": "Creator not authenticated with TikTok"}
            
            # Check if token is expired and refresh if needed
            if auth.token_expires_at and auth.token_expires_at < datetime.utcnow():
                await self._refresh_token(auth)
            
            # Fetch videos from TikTok API (mocked for now)
            videos_data = await self._fetch_videos_from_tiktok(auth)
            
            synced_count = 0
            updated_count = 0
            
            for video_data in videos_data:
                existing_video = await self._get_video_by_tiktok_id(video_data["id"])
                
                if existing_video:
                    # Update existing video
                    await self._update_video_metrics(existing_video, video_data)
                    updated_count += 1
                else:
                    # Create new video record
                    await self._create_video_record(creator_id, video_data)
                    synced_count += 1
            
            await self.db.commit()
            
            # Update last sync time
            await self._update_last_sync(creator_id)
            
            return {
                "success": True,
                "synced_videos": synced_count,
                "updated_videos": updated_count,
                "total_processed": len(videos_data)
            }
            
        except Exception as e:
            logger.error(f"Error syncing videos for creator {creator_id}: {str(e)}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def mark_video_as_deliverable(
        self, 
        video_id: str, 
        campaign_id: str, 
        deliverable_type: str = "post"
    ) -> Dict[str, Any]:
        """Mark a video as a campaign deliverable"""
        try:
            # Get video details
            video_query = select(TikTokVideo).where(TikTokVideo.id == video_id)
            video_result = await self.db.execute(video_query)
            video = video_result.scalar_one_or_none()
            
            if not video:
                return {"success": False, "error": "Video not found"}
            
            # Check if deliverable already exists
            existing_query = select(CampaignVideoDeliverable).where(
                and_(
                    CampaignVideoDeliverable.video_id == video_id,
                    CampaignVideoDeliverable.campaign_id == campaign_id
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                return {"success": False, "error": "Video already marked as deliverable for this campaign"}
            
            # Create deliverable record
            deliverable = CampaignVideoDeliverable(
                campaign_id=campaign_id,
                video_id=video_id,
                creator_id=video.creator_id,
                deliverable_type=deliverable_type,
                status=DeliverableStatus.PENDING,
                submitted_at=datetime.utcnow(),
                requirements_met=self._check_requirements(video, deliverable_type)
            )
            
            self.db.add(deliverable)
            await self.db.commit()
            
            return {
                "success": True,
                "deliverable_id": str(deliverable.id),
                "status": deliverable.status.value
            }
            
        except Exception as e:
            logger.error(f"Error marking video as deliverable: {str(e)}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def calculate_gmv_attribution(
        self, 
        video_id: str, 
        attribution_window_hours: int = 72
    ) -> Dict[str, Any]:
        """Calculate GMV attribution for a video based on orders within attribution window"""
        try:
            # Get video details
            video_query = select(TikTokVideo).where(TikTokVideo.id == video_id)
            video_result = await self.db.execute(video_query)
            video = video_result.scalar_one_or_none()
            
            if not video:
                return {"success": False, "error": "Video not found"}
            
            # Define attribution window
            window_start = video.published_at
            window_end = window_start + timedelta(hours=attribution_window_hours)
            
            # Find orders within attribution window
            orders_query = select(TikTokOrder).where(
                and_(
                    TikTokOrder.creator_id == video.creator_id,
                    TikTokOrder.order_date >= window_start,
                    TikTokOrder.order_date <= window_end,
                    or_(
                        TikTokOrder.attributed_video_id == None,
                        TikTokOrder.attributed_video_id == video_id
                    )
                )
            )
            orders_result = await self.db.execute(orders_query)
            orders = orders_result.scalars().all()
            
            total_gmv = 0
            attributed_orders = 0
            attribution_updates = []
            
            for order in orders:
                # Calculate attribution confidence based on method
                confidence = self._calculate_attribution_confidence(order, video)
                
                if confidence > 0.5:  # Threshold for attribution
                    # Update order with video attribution
                    order.attributed_video_id = video_id
                    order.attribution_confidence = confidence
                    
                    total_gmv += order.total_amount
                    attributed_orders += 1
                    attribution_updates.append({
                        "order_id": str(order.id),
                        "amount": order.total_amount,
                        "confidence": confidence
                    })
            
            # Update video metrics
            await self._update_video_gmv_metrics(video_id, total_gmv, attributed_orders)
            
            await self.db.commit()
            
            return {
                "success": True,
                "video_id": video_id,
                "total_attributed_gmv": total_gmv,
                "attributed_orders_count": attributed_orders,
                "attribution_details": attribution_updates
            }
            
        except Exception as e:
            logger.error(f"Error calculating GMV attribution: {str(e)}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def update_video_metrics(self, video_id: str) -> Dict[str, Any]:
        """Update video metrics from TikTok API"""
        try:
            # Get video and creator auth
            video_query = select(TikTokVideo).options(
                selectinload(TikTokVideo.metrics)
            ).where(TikTokVideo.id == video_id)
            video_result = await self.db.execute(video_query)
            video = video_result.scalar_one_or_none()
            
            if not video:
                return {"success": False, "error": "Video not found"}
            
            # Fetch updated metrics from TikTok API (mocked for now)
            updated_metrics = await self._fetch_video_metrics_from_tiktok(video.tiktok_video_id)
            
            # Update video record
            video.view_count = updated_metrics["view_count"]
            video.like_count = updated_metrics["like_count"]
            video.comment_count = updated_metrics["comment_count"]
            video.share_count = updated_metrics["share_count"]
            video.updated_at = datetime.utcnow()
            
            # Create metrics snapshot
            metrics_record = TikTokVideoMetrics(
                video_id=video_id,
                view_count=updated_metrics["view_count"],
                like_count=updated_metrics["like_count"],
                comment_count=updated_metrics["comment_count"],
                share_count=updated_metrics["share_count"],
                engagement_rate=self._calculate_engagement_rate(updated_metrics),
                engagement_count=updated_metrics["like_count"] + updated_metrics["comment_count"] + updated_metrics["share_count"]
            )
            
            self.db.add(metrics_record)
            await self.db.commit()
            
            return {
                "success": True,
                "metrics": {
                    "views": updated_metrics["view_count"],
                    "likes": updated_metrics["like_count"],
                    "comments": updated_metrics["comment_count"],
                    "shares": updated_metrics["share_count"],
                    "engagement_rate": metrics_record.engagement_rate
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating video metrics: {str(e)}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def get_creator_video_performance(self, creator_id: str, timeframe_days: int = 30) -> Dict[str, Any]:
        """Get comprehensive video performance data for a creator"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=timeframe_days)
            
            # Get videos with metrics
            videos_query = select(TikTokVideo).options(
                selectinload(TikTokVideo.metrics),
                selectinload(TikTokVideo.attributed_orders)
            ).where(
                and_(
                    TikTokVideo.creator_id == creator_id,
                    TikTokVideo.published_at >= cutoff_date,
                    TikTokVideo.status == VideoStatus.ACTIVE
                )
            )
            videos_result = await self.db.execute(videos_query)
            videos = videos_result.scalars().all()
            
            # Calculate aggregate metrics
            total_videos = len(videos)
            total_views = sum(video.view_count for video in videos)
            total_likes = sum(video.like_count for video in videos)
            total_comments = sum(video.comment_count for video in videos)
            total_shares = sum(video.share_count for video in videos)
            
            # Calculate GMV attribution
            total_gmv = 0
            total_attributed_orders = 0
            
            for video in videos:
                if video.attributed_orders:
                    video_gmv = sum(order.total_amount for order in video.attributed_orders)
                    total_gmv += video_gmv
                    total_attributed_orders += len(video.attributed_orders)
            
            # Calculate averages
            avg_views = total_views / total_videos if total_videos > 0 else 0
            avg_engagement_rate = self._calculate_engagement_rate({
                "view_count": total_views,
                "like_count": total_likes,
                "comment_count": total_comments,
                "share_count": total_shares
            })
            
            return {
                "success": True,
                "creator_id": creator_id,
                "timeframe_days": timeframe_days,
                "performance": {
                    "total_videos": total_videos,
                    "total_views": total_views,
                    "total_likes": total_likes,
                    "total_comments": total_comments,
                    "total_shares": total_shares,
                    "avg_views_per_video": avg_views,
                    "avg_engagement_rate": avg_engagement_rate,
                    "total_attributed_gmv": total_gmv,
                    "total_attributed_orders": total_attributed_orders,
                    "avg_gmv_per_video": total_gmv / total_videos if total_videos > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting creator video performance: {str(e)}")
            return {"success": False, "error": str(e)}

    # Private helper methods
    async def _fetch_videos_from_tiktok(self, auth: TikTokCreatorAuth) -> List[Dict[str, Any]]:
        """Fetch videos from TikTok API"""
        try:
            # TikTok for Business API endpoint for user videos
            url = f"{self.tiktok_api_base}/v2/user/videos/"
            
            headers = {
                "Authorization": f"Bearer {auth.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "user_id": auth.tiktok_user_id,
                "fields": "id,title,description,video_url,thumbnail_url,view_count,like_count,comment_count,share_count,published_at",
                "max_count": 20  # Adjust as needed
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("error"):
                    logger.error(f"TikTok API error: {data['error']}")
                    return []
                
                videos = []
                for video_data in data.get("data", []):
                    videos.append({
                        "id": video_data.get("id"),
                        "title": video_data.get("title", ""),
                        "description": video_data.get("description", ""),
                        "view_count": video_data.get("view_count", 0),
                        "like_count": video_data.get("like_count", 0),
                        "comment_count": video_data.get("comment_count", 0),
                        "share_count": video_data.get("share_count", 0),
                        "published_at": self._parse_tiktok_timestamp(video_data.get("published_at")),
                        "video_url": video_data.get("video_url", ""),
                        "thumbnail_url": video_data.get("thumbnail_url", "")
                    })
                
                logger.info(f"Successfully fetched {len(videos)} videos from TikTok API")
                return videos
                
        except httpx.HTTPStatusError as e:
            logger.error(f"TikTok API HTTP error: {e.response.status_code} - {e.response.text}")
            # Fallback to empty list or minimal mock data
            return []
        except Exception as e:
            logger.error(f"Error fetching videos from TikTok API: {str(e)}")
            # Fallback to empty list
            return []

    async def _fetch_video_metrics_from_tiktok(self, tiktok_video_id: str) -> Dict[str, Any]:
        """Fetch video metrics from TikTok API"""
        try:
            # TikTok for Business API endpoint for video metrics
            url = f"{self.tiktok_api_base}/v2/video/metrics/"
            
            # You'll need to get auth for this request
            # This is simplified - you may need to handle auth differently
            headers = {
                "Authorization": f"Bearer {self._get_app_access_token()}",
                "Content-Type": "application/json"
            }
            
            params = {
                "video_id": tiktok_video_id,
                "fields": "view_count,like_count,comment_count,share_count"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("error"):
                    logger.error(f"TikTok API error for video {tiktok_video_id}: {data['error']}")
                    return {}
                
                metrics = data.get("data", {})
                return {
                    "view_count": metrics.get("view_count", 0),
                    "like_count": metrics.get("like_count", 0),
                    "comment_count": metrics.get("comment_count", 0),
                    "share_count": metrics.get("share_count", 0)
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"TikTok API HTTP error for video {tiktok_video_id}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching metrics for video {tiktok_video_id}: {str(e)}")
            return {}

    def _parse_tiktok_timestamp(self, timestamp: str) -> datetime:
        """Parse TikTok timestamp to datetime object"""
        try:
            if timestamp:
                # TikTok typically returns Unix timestamps
                if isinstance(timestamp, (int, float)):
                    return datetime.fromtimestamp(timestamp)
                elif isinstance(timestamp, str) and timestamp.isdigit():
                    return datetime.fromtimestamp(int(timestamp))
                else:
                    # Try to parse as ISO format
                    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return datetime.utcnow()
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp: {timestamp}")
            return datetime.utcnow()

    def _get_app_access_token(self) -> str:
        """Get app-level access token for TikTok API"""
        # This should be implemented to get/refresh app access token
        # For now, you might want to store this in your config or database
        from app.core.config import settings
        return settings.TIKTOK_APP_ACCESS_TOKEN if hasattr(settings, 'TIKTOK_APP_ACCESS_TOKEN') else ""

    def _calculate_engagement_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate engagement rate from video metrics"""
        views = metrics.get("view_count", 0)
        if views == 0:
            return 0.0
        
        engagements = (
            metrics.get("like_count", 0) + 
            metrics.get("comment_count", 0) + 
            metrics.get("share_count", 0)
        )
        
        return (engagements / views) * 100

    def _calculate_attribution_confidence(self, order: TikTokOrder, video: TikTokVideo) -> float:
        """Calculate attribution confidence score"""
        confidence = 0.0
        
        # Time-based confidence (closer to video publish = higher confidence)
        time_diff = (order.order_date - video.published_at).total_seconds() / 3600  # hours
        if time_diff <= 24:
            confidence += 0.4
        elif time_diff <= 48:
            confidence += 0.3
        elif time_diff <= 72:
            confidence += 0.2
        
        # Promo code match
        if order.promo_code_used and video.promo_codes:
            if order.promo_code_used in video.promo_codes:
                confidence += 0.5
        
        # Direct link tracking
        if order.attribution_method == AttributionMethod.DIRECT_LINK:
            confidence += 0.3
        
        return min(confidence, 1.0)

    async def _get_video_by_tiktok_id(self, tiktok_video_id: str) -> Optional[TikTokVideo]:
        """Get video by TikTok video ID"""
        query = select(TikTokVideo).where(TikTokVideo.tiktok_video_id == tiktok_video_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _create_video_record(self, creator_id: str, video_data: Dict[str, Any]) -> TikTokVideo:
        """Create new video record from TikTok data"""
        video = TikTokVideo(
            creator_id=creator_id,
            tiktok_video_id=video_data["id"],
            title=video_data.get("title"),
            description=video_data.get("description"),
            video_url=video_data.get("video_url"),
            thumbnail_url=video_data.get("thumbnail_url"),
            view_count=video_data.get("view_count", 0),
            like_count=video_data.get("like_count", 0),
            comment_count=video_data.get("comment_count", 0),
            share_count=video_data.get("share_count", 0),
            published_at=video_data.get("published_at"),
            status=VideoStatus.ACTIVE
        )
        
        self.db.add(video)
        return video

    async def _update_video_metrics(self, video: TikTokVideo, video_data: Dict[str, Any]):
        """Update existing video with new metrics"""
        video.view_count = video_data.get("view_count", video.view_count)
        video.like_count = video_data.get("like_count", video.like_count)
        video.comment_count = video_data.get("comment_count", video.comment_count)
        video.share_count = video_data.get("share_count", video.share_count)
        video.updated_at = datetime.utcnow()

    async def _update_video_gmv_metrics(self, video_id: str, total_gmv: float, attributed_orders: int):
        """Update video's GMV attribution metrics"""
        # Update latest metrics record or create new one
        latest_metrics_query = select(TikTokVideoMetrics).where(
            TikTokVideoMetrics.video_id == video_id
        ).order_by(TikTokVideoMetrics.recorded_at.desc()).limit(1)
        
        result = await self.db.execute(latest_metrics_query)
        latest_metrics = result.scalar_one_or_none()
        
        if latest_metrics:
            latest_metrics.attributed_gmv = total_gmv
            latest_metrics.attributed_orders = attributed_orders
        
    def _check_requirements(self, video: TikTokVideo, deliverable_type: str) -> Dict[str, Any]:
        """Check if video meets campaign requirements"""
        # Mock requirements check - replace with actual logic
        return {
            "has_hashtags": True,
            "min_duration_met": True,
            "brand_mention": True,
            "content_guidelines": True
        }

    async def _refresh_token(self, auth: TikTokCreatorAuth):
        """Refresh TikTok access token"""
        # Mock token refresh - implement actual refresh logic
        auth.token_expires_at = datetime.utcnow() + timedelta(hours=24)
        
    async def _update_last_sync(self, creator_id: str):
        """Update last sync timestamp for creator"""
        update_query = update(TikTokCreatorAuth).where(
            TikTokCreatorAuth.creator_id == creator_id
        ).values(last_sync_at=datetime.utcnow())
        
        await self.db.execute(update_query) 