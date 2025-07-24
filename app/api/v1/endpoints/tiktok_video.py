"""
TikTok Video Integration Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging

from app.core.database import get_db
from app.services.tiktok_video_service import TikTokVideoService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sync-videos")
async def sync_creator_videos(
    creator_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync TikTok videos for a specific creator
    """
    try:
        video_service = TikTokVideoService(db)
        result = await video_service.sync_creator_videos(creator_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "synced_count": result["synced_count"],
                    "total_videos": result["total_videos"]
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error syncing videos for creator {creator_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync videos: {str(e)}")


@router.post("/mark-deliverable")
async def mark_video_as_deliverable(
    video_id: str,
    deliverable_id: str,
    creator_id: str,
    campaign_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Mark a TikTok video as a campaign deliverable
    """
    try:
        video_service = TikTokVideoService(db)
        result = await video_service.mark_video_as_deliverable(
            video_id=video_id,
            deliverable_id=deliverable_id,
            creator_id=creator_id,
            campaign_id=campaign_id
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "video_id": video_id,
                    "deliverable_id": deliverable_id,
                    "campaign_id": campaign_id,
                    "creator_id": creator_id
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error marking video {video_id} as deliverable: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mark video as deliverable: {str(e)}")


@router.post("/attribute-gmv")
async def calculate_gmv_attribution(
    creator_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate GMV attribution for a creator's videos
    """
    try:
        video_service = TikTokVideoService(db)
        result = await video_service.calculate_gmv_attribution(creator_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "total_attributed_gmv": result["total_attributed_gmv"],
                    "total_attributed_orders": result["total_attributed_orders"],
                    "videos_processed": result["videos_processed"]
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error calculating GMV attribution for creator {creator_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate GMV attribution: {str(e)}")


@router.get("/creator/{creator_id}/performance")
async def get_creator_video_performance(
    creator_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get video performance summary for a creator
    """
    try:
        video_service = TikTokVideoService(db)
        result = await video_service.get_creator_video_performance(creator_id)
        
        if result["success"]:
            return {
                "success": True,
                "data": result["performance"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error getting video performance for creator {creator_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get video performance: {str(e)}")


@router.post("/videos/{video_id}/update-metrics")
async def update_video_metrics(
    video_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update metrics for a specific video
    """
    try:
        video_service = TikTokVideoService(db)
        result = await video_service.update_video_metrics(video_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": result["metrics"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error updating metrics for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update video metrics: {str(e)}") 