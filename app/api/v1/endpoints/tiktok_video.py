from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from pydantic import BaseModel
import uuid

from app.models.database import get_db
from app.services.tiktok_video_service import TikTokVideoService

router = APIRouter()

# Pydantic models for request/response
class SyncVideosRequest(BaseModel):
    creator_id: str
    force_sync: bool = False

class MarkDeliverableRequest(BaseModel):
    video_id: str
    campaign_id: str
    deliverable_type: str = "post"

class AttributeGMVRequest(BaseModel):
    video_id: str
    attribution_window_hours: int = 72

class UpdateMetricsRequest(BaseModel):
    video_id: str

@router.post("/sync-videos")
async def sync_creator_videos(
    request: SyncVideosRequest,
    db: AsyncSession = Depends(get_db)
):
    """Sync TikTok videos for a creator from TikTok API"""
    service = TikTokVideoService(db)
    
    try:
        result = await service.sync_creator_videos(
            creator_id=request.creator_id,
            force_sync=request.force_sync
        )
        
        if result["success"]:
            return {
                "message": "Videos synced successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mark-deliverable")
async def mark_video_as_deliverable(
    request: MarkDeliverableRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mark a video as a campaign deliverable"""
    service = TikTokVideoService(db)
    
    try:
        result = await service.mark_video_as_deliverable(
            video_id=request.video_id,
            campaign_id=request.campaign_id,
            deliverable_type=request.deliverable_type
        )
        
        if result["success"]:
            return {
                "message": "Video marked as deliverable successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/attribute-gmv")
async def calculate_gmv_attribution(
    request: AttributeGMVRequest,
    db: AsyncSession = Depends(get_db)
):
    """Calculate GMV attribution for a video"""
    service = TikTokVideoService(db)
    
    try:
        result = await service.calculate_gmv_attribution(
            video_id=request.video_id,
            attribution_window_hours=request.attribution_window_hours
        )
        
        if result["success"]:
            return {
                "message": "GMV attribution calculated successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/creator/{creator_id}/performance")
async def get_creator_video_performance(
    creator_id: str,
    timeframe_days: int = Query(30, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive video performance data for a creator"""
    service = TikTokVideoService(db)
    
    try:
        # Validate creator_id format
        try:
            uuid.UUID(creator_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid creator ID format")
        
        result = await service.get_creator_video_performance(
            creator_id=creator_id,
            timeframe_days=timeframe_days
        )
        
        if result["success"]:
            return {
                "message": "Creator performance data retrieved successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/videos/{video_id}/update-metrics")
async def update_video_metrics(
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Update video metrics from TikTok API"""
    service = TikTokVideoService(db)
    
    try:
        # Validate video_id format
        try:
            uuid.UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid video ID format")
        
        result = await service.update_video_metrics(video_id=video_id)
        
        if result["success"]:
            return {
                "message": "Video metrics updated successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}/attribution")
async def get_video_attribution(
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get GMV attribution details for a specific video"""
    service = TikTokVideoService(db)
    
    try:
        # Validate video_id format
        try:
            uuid.UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid video ID format")
        
        # This would be a new method in the service
        # For now, return mock data
        return {
            "message": "Video attribution data retrieved successfully",
            "data": {
                "video_id": video_id,
                "total_attributed_gmv": 2500.75,
                "attributed_orders_count": 15,
                "attribution_confidence": 0.85,
                "attribution_method": "direct_link",
                "attribution_window_hours": 72
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/creator/{creator_id}/videos")
async def get_creator_videos(
    creator_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by video status"),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of creator's TikTok videos"""
    try:
        # Validate creator_id format
        try:
            uuid.UUID(creator_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid creator ID format")
        
        # Mock data for now - implement actual database query
        return {
            "message": "Creator videos retrieved successfully",
            "data": {
                "videos": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "tiktok_video_id": "7123456789012345678",
                        "title": "Summer Fashion Haul #fashion #style",
                        "view_count": 125000,
                        "like_count": 8500,
                        "comment_count": 450,
                        "share_count": 320,
                        "engagement_rate": 7.4,
                        "attributed_gmv": 2500.75,
                        "published_at": "2024-05-15T10:30:00Z",
                        "status": "active"
                    }
                ],
                "pagination": {
                    "total": 45,
                    "limit": limit,
                    "offset": offset,
                    "has_more": True
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/campaign/{campaign_id}/deliverables")
async def get_campaign_deliverables(
    campaign_id: str,
    status: Optional[str] = Query(None, description="Filter by deliverable status"),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign deliverables with video details"""
    try:
        # Validate campaign_id format
        try:
            uuid.UUID(campaign_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid campaign ID format")
        
        # Mock data for now - implement actual database query
        return {
            "message": "Campaign deliverables retrieved successfully",
            "data": {
                "deliverables": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440002",
                        "video_id": "550e8400-e29b-41d4-a716-446655440001",
                        "creator_id": "550e8400-e29b-41d4-a716-446655440003",
                        "deliverable_type": "post",
                        "status": "approved",
                        "submitted_at": "2024-05-15T10:30:00Z",
                        "approved_at": "2024-05-15T14:20:00Z",
                        "performance_score": 92.5,
                        "bonus_eligible": True,
                        "video": {
                            "title": "Summer Fashion Haul #fashion #style",
                            "view_count": 125000,
                            "attributed_gmv": 2500.75
                        }
                    }
                ],
                "summary": {
                    "total_deliverables": 12,
                    "pending": 3,
                    "approved": 8,
                    "rejected": 1,
                    "total_attributed_gmv": 15420.50
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/connect")
async def connect_tiktok_account(
    creator_id: str = Body(...),
    auth_code: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Connect creator's TikTok account using OAuth flow"""
    try:
        # Validate creator_id format
        try:
            uuid.UUID(creator_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid creator ID format")
        
        # Mock OAuth flow - implement actual TikTok OAuth
        # This would exchange auth_code for access_token
        
        return {
            "message": "TikTok account connected successfully",
            "data": {
                "creator_id": creator_id,
                "tiktok_username": "@sarahstyles",
                "display_name": "Sarah Johnson",
                "is_connected": True,
                "scopes": ["user.info.basic", "video.list", "video.upload"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth/{creator_id}/disconnect")
async def disconnect_tiktok_account(
    creator_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Disconnect creator's TikTok account"""
    try:
        # Validate creator_id format
        try:
            uuid.UUID(creator_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid creator ID format")
        
        # Mock disconnection - implement actual logic to revoke tokens and delete auth record
        
        return {
            "message": "TikTok account disconnected successfully",
            "data": {
                "creator_id": creator_id,
                "is_connected": False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 