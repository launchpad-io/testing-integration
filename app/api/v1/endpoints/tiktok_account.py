# app/api/v1/endpoints/tiktok_account.py - Updated with PKCE support
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_async_db
from app.models.tiktok_models import TikTokAccount
from app.services.tiktok_account_service import TikTokAccountService
from typing import Optional
import uuid
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status/{user_id}")
async def get_tiktok_connection_status(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get TikTok connection status for a user"""
    try:
        account_service = TikTokAccountService(db)
        status = await account_service.get_connection_status(user_id)
        return status
    except Exception as e:
        logger.error(f"Failed to get connection status for user {user_id}: {str(e)}", exc_info=True)
        # Return safe fallback response instead of raising error
        return {
            "success": True,
            "data": {
                "status": "disconnected",
                "username": None,
                "userId": None,
                "connectedAt": None,
                "lastSync": None,
                "error": None
            }
        }

@router.post("/auth/init")
async def init_tiktok_auth(
    user_id: str = Query(...),
    redirect_uri: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_async_db)
):
    """Initialize TikTok OAuth authentication with PKCE"""
    try:
        # Validate PKCE method
        if code_challenge_method != "S256":
            raise HTTPException(
                status_code=400, 
                detail="Only S256 code challenge method is supported"
            )
        
        account_service = TikTokAccountService(db)
        auth_data = await account_service.init_auth(
            user_id=user_id, 
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            state=state
        )
        return auth_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize auth: {str(e)}")

@router.post("/auth/callback")
async def handle_tiktok_auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    user_id: str = Query(...),
    code_verifier: str = Query(...),
    db: AsyncSession = Depends(get_async_db)
):
    """Handle TikTok OAuth callback with PKCE verification"""
    try:
        account_service = TikTokAccountService(db)
        status = await account_service.handle_auth_callback(
            code=code, 
            state=state, 
            user_id=user_id,
            code_verifier=code_verifier
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to handle auth callback: {str(e)}")

@router.delete("/disconnect/{user_id}")
async def disconnect_tiktok(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Disconnect TikTok account"""
    try:
        account_service = TikTokAccountService(db)
        result = await account_service.disconnect_account(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect account: {str(e)}")

@router.post("/sync/{user_id}")
async def sync_tiktok_data(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Sync TikTok account data"""
    try:
        account_service = TikTokAccountService(db)
        result = await account_service.sync_account_data(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync account data: {str(e)}")

@router.get("/metrics/{user_id}")
async def get_tiktok_metrics(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get TikTok account metrics"""
    try:
        account_service = TikTokAccountService(db)
        metrics = await account_service.get_account_metrics(user_id)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")