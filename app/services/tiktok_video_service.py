"""
TikTok Video Service for video syncing, deliverable tracking, and GMV attribution
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import selectinload

from app.models.tiktok_models import (
    TikTokVideo, 
    TikTokVideoMetrics, 
    TikTokOrder, 
    TikTokAccount,
    CampaignVideoDeliverable
)
from app.external.tiktok_api import TikTokAPIClient

logger = logging.getLogger(__name__)


class TikTokVideoService:
    """Service for TikTok video operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tiktok_client = TikTokAPIClient()
    
    async def sync_creator_videos(self, creator_id: str) -> Dict[str, Any]:
        """Sync videos for a specific creator"""
        try:
            # Get creator's TikTok account
            account_query = select(TikTokAccount).where(
                and_(
                    TikTokAccount.user_id == creator_id,
                    TikTokAccount.is_active == True
                )
            )
            account_result = await self.session.execute(account_query)
            account = account_result.scalar_one_or_none()
            
            if not account:
                raise ValueError(f"No active TikTok account found for creator {creator_id}")
            
            # Fetch videos from TikTok API
            videos_data = await self.tiktok_client.get_creator_videos(account.tiktok_user_id)
            
            synced_count = 0
            new_videos = []
            
            for video_data in videos_data.get('videos', []):
                # Check if video already exists
                existing_video = await self.session.execute(
                    select(TikTokVideo).where(TikTokVideo.video_id == video_data['id'])
                )
                
                if not existing_video.scalar_one_or_none():
                    # Create new video record
                    video = TikTokVideo(
                        id=f"video_{video_data['id']}",
                        account_id=account.id,
                        video_id=video_data['id'],
                        title=video_data.get('title', ''),
                        description=video_data.get('description', ''),
                        view_count=video_data.get('stats', {}).get('view_count', 0),
                        like_count=video_data.get('stats', {}).get('like_count', 0),
                        comment_count=video_data.get('stats', {}).get('comment_count', 0),
                        share_count=video_data.get('stats', {}).get('share_count', 0),
                        play_count=video_data.get('stats', {}).get('play_count', 0),
                        duration=video_data.get('duration', 0),
                        video_url=video_data.get('video', {}).get('play_addr', {}).get('url_list', [None])[0],
                        share_url=video_data.get('share_url', ''),
                        cover_image_url=video_data.get('video', {}).get('cover', {}).get('url_list', [None])[0],
                        dynamic_cover_url=video_data.get('video', {}).get('dynamic_cover', {}).get('url_list', [None])[0],
                        video_status=video_data.get('status', 'public'),
                        created_at=datetime.fromtimestamp(video_data.get('create_time', 0)),
                        discovered_at=datetime.utcnow()
                    )
                    
                    new_videos.append(video)
                    synced_count += 1
            
            # Save new videos
            if new_videos:
                self.session.add_all(new_videos)
                await self.session.commit()
            
            # Update account last sync time
            await self.session.execute(
                update(TikTokAccount)
                .where(TikTokAccount.id == account.id)
                .values(last_sync_at=datetime.utcnow())
            )
            await self.session.commit()
            
            return {
                "success": True,
                "synced_count": synced_count,
                "total_videos": len(videos_data.get('videos', [])),
                "message": f"Successfully synced {synced_count} new videos"
            }
            
        except Exception as e:
            logger.error(f"Error syncing videos for creator {creator_id}: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def mark_video_as_deliverable(
        self, 
        video_id: str, 
        deliverable_id: str, 
        creator_id: str,
        campaign_id: str
    ) -> Dict[str, Any]:
        """Mark a video as a campaign deliverable"""
        try:
            # Get the video
            video_query = select(TikTokVideo).where(TikTokVideo.video_id == video_id)
            video_result = await self.session.execute(video_query)
            video = video_result.scalar_one_or_none()
            
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            # Update video as deliverable
            await self.session.execute(
                update(TikTokVideo)
                .where(TikTokVideo.video_id == video_id)
                .values(
                    is_deliverable=True,
                    deliverable_id=deliverable_id,
                    campaign_id=campaign_id,
                    deliverable_status="pending"
                )
            )
            
            # Create campaign video deliverable record
            deliverable = CampaignVideoDeliverable(
                id=f"deliverable_{deliverable_id}_{video_id}",
                campaign_id=campaign_id,
                deliverable_id=deliverable_id,
                creator_id=creator_id,
                video_id=video_id,
                status="pending",
                submitted_at=datetime.utcnow()
            )
            
            self.session.add(deliverable)
            await self.session.commit()
            
            return {
                "success": True,
                "message": f"Video {video_id} marked as deliverable for campaign {campaign_id}"
            }
            
        except Exception as e:
            logger.error(f"Error marking video as deliverable: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def calculate_gmv_attribution(self, creator_id: str) -> Dict[str, Any]:
        """Calculate GMV attribution for a creator's videos"""
        try:
            # Get all videos for the creator
            videos_query = select(TikTokVideo).where(
                and_(
                    TikTokVideo.account_id.in_(
                        select(TikTokAccount.id).where(TikTokAccount.user_id == creator_id)
                    ),
                    TikTokVideo.is_deliverable == True
                )
            )
            videos_result = await self.session.execute(videos_query)
            videos = videos_result.scalars().all()
            
            total_attributed_gmv = Decimal('0.00')
            total_attributed_orders = 0
            
            for video in videos:
                # Get orders that can be attributed to this video
                # This is a simplified attribution model - in production you'd use more sophisticated logic
                orders_query = select(TikTokOrder).where(
                    and_(
                        TikTokOrder.creator_id == creator_id,
                        TikTokOrder.attributed_video_id.is_(None),  # Not yet attributed
                        TikTokOrder.total_amount > 0
                    )
                )
                orders_result = await self.session.execute(orders_query)
                orders = orders_result.scalars().all()
                
                # Simple attribution: attribute orders based on video performance
                # In production, you'd use more sophisticated attribution models
                video_engagement = (video.like_count + video.comment_count + video.share_count) / max(video.view_count, 1)
                
                for order in orders:
                    # Calculate attribution confidence based on engagement
                    attribution_confidence = min(video_engagement * 100, 1.0)
                    
                    # Attribute a portion of the order to this video
                    attributed_amount = order.total_amount * Decimal(str(attribution_confidence))
                    
                    # Update order with attribution
                    await self.session.execute(
                        update(TikTokOrder)
                        .where(TikTokOrder.id == order.id)
                        .values(
                            attributed_video_id=video.video_id,
                            attribution_method="engagement_based",
                            attribution_confidence=attribution_confidence
                        )
                    )
                    
                    # Update video with attributed GMV
                    video.attributed_gmv += attributed_amount
                    video.attributed_orders += 1
                    video.last_attribution_update = datetime.utcnow()
                    
                    total_attributed_gmv += attributed_amount
                    total_attributed_orders += 1
            
            await self.session.commit()
            
            return {
                "success": True,
                "total_attributed_gmv": float(total_attributed_gmv),
                "total_attributed_orders": total_attributed_orders,
                "videos_processed": len(videos),
                "message": f"Attributed ${total_attributed_gmv:.2f} GMV across {total_attributed_orders} orders"
            }
            
        except Exception as e:
            logger.error(f"Error calculating GMV attribution for creator {creator_id}: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_video_metrics(self, video_id: str) -> Dict[str, Any]:
        """Update metrics for a specific video"""
        try:
            # Get video
            video_query = select(TikTokVideo).where(TikTokVideo.video_id == video_id)
            video_result = await self.session.execute(video_query)
            video = video_result.scalar_one_or_none()
            
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            # Fetch updated metrics from TikTok API
            metrics_data = await self.tiktok_client.get_video_metrics(video_id)
            
            # Update video metrics
            await self.session.execute(
                update(TikTokVideo)
                .where(TikTokVideo.video_id == video_id)
                .values(
                    view_count=metrics_data.get('view_count', video.view_count),
                    like_count=metrics_data.get('like_count', video.like_count),
                    comment_count=metrics_data.get('comment_count', video.comment_count),
                    share_count=metrics_data.get('share_count', video.share_count),
                    play_count=metrics_data.get('play_count', video.play_count),
                    updated_at=datetime.utcnow()
                )
            )
            
            # Create metrics snapshot
            engagement_rate = 0
            if video.view_count > 0:
                engagement_rate = ((video.like_count + video.comment_count + video.share_count) / video.view_count) * 100
            
            metrics_snapshot = TikTokVideoMetrics(
                id=f"metrics_{video_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                video_id=video_id,
                view_count=metrics_data.get('view_count', video.view_count),
                like_count=metrics_data.get('like_count', video.like_count),
                comment_count=metrics_data.get('comment_count', video.comment_count),
                share_count=metrics_data.get('share_count', video.share_count),
                play_count=metrics_data.get('play_count', video.play_count),
                engagement_rate=engagement_rate,
                view_velocity=metrics_data.get('view_velocity', 0)
            )
            
            self.session.add(metrics_snapshot)
            await self.session.commit()
            
            return {
                "success": True,
                "message": f"Updated metrics for video {video_id}",
                "metrics": {
                    "view_count": metrics_data.get('view_count', video.view_count),
                    "like_count": metrics_data.get('like_count', video.like_count),
                    "comment_count": metrics_data.get('comment_count', video.comment_count),
                    "share_count": metrics_data.get('share_count', video.share_count),
                    "engagement_rate": engagement_rate
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating metrics for video {video_id}: {str(e)}")
            await self.session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_creator_video_performance(self, creator_id: str) -> Dict[str, Any]:
        """Get video performance summary for a creator"""
        try:
            # Get all videos for the creator
            videos_query = select(TikTokVideo).where(
                TikTokVideo.account_id.in_(
                    select(TikTokAccount.id).where(TikTokAccount.user_id == creator_id)
                )
            )
            videos_result = await self.session.execute(videos_query)
            videos = videos_result.scalars().all()
            
            total_views = sum(v.view_count for v in videos)
            total_likes = sum(v.like_count for v in videos)
            total_comments = sum(v.comment_count for v in videos)
            total_shares = sum(v.share_count for v in videos)
            total_attributed_gmv = sum(v.attributed_gmv for v in videos)
            
            avg_engagement_rate = 0
            if total_views > 0:
                avg_engagement_rate = ((total_likes + total_comments + total_shares) / total_views) * 100
            
            deliverable_videos = [v for v in videos if v.is_deliverable]
            
            return {
                "success": True,
                "performance": {
                    "total_videos": len(videos),
                    "deliverable_videos": len(deliverable_videos),
                    "total_views": total_views,
                    "total_likes": total_likes,
                    "total_comments": total_comments,
                    "total_shares": total_shares,
                    "avg_engagement_rate": float(avg_engagement_rate),
                    "total_attributed_gmv": float(total_attributed_gmv),
                    "total_attributed_orders": sum(v.attributed_orders for v in videos)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting video performance for creator {creator_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            } 