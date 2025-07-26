# app/services/tiktok_business_auth_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.tiktok_models import TikTokAccount
from app.core.config import settings
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import httpx
import logging
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)

class TikTokBusinessAuthService:
    """Service for TikTok for Business (TT4D) authentication"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # TikTok for Business credentials
        self.client_key = settings.TIKTOK_CLIENT_KEY
        self.client_secret = settings.TIKTOK_CLIENT_SECRET
        self.app_id = settings.TIKTOK_APP_ID
        self.developer_id = settings.TIKTOK_DEVELOPER_ID
        self.app_name = "LaunchPAID"
        
        # TikTok for Business URLs
        self.auth_base_url = settings.TIKTOK_BUSINESS_API_URL
        self.login_base_url = "https://www.tiktok.com"
        
    async def get_auth_url(
        self, 
        user_id: str, 
        redirect_uri: str,
        auth_type: str = "USER_AUTH"  # USER_AUTH for creators, BUSINESS_AUTH for shops
    ) -> Dict[str, Any]:
        """Generate TikTok for Business authentication URL"""
        try:
            # Generate state for security
            state = f"{user_id}_{datetime.utcnow().timestamp()}"
            
            # For USER_AUTH (creators)
            if auth_type == "USER_AUTH":
                # Build the authorization URL
                auth_params = {
                    "client_key": self.client_key,
                    "response_type": "code",
                    "scope": "user.info.basic,video.list,video.insights",
                    "redirect_uri": redirect_uri,
                    "state": state
                }
                
                auth_url = f"{self.auth_base_url}/portal/auth?" + urlencode(auth_params)
                
            else:  # BUSINESS_AUTH (shops)
                # For Business/Shop authentication
                auth_params = {
                    "app_id": self.app_id,
                    "state": state,
                    "redirect_uri": redirect_uri
                }
                
                # This matches your sandbox URL pattern
                auth_url = f"{self.auth_base_url}/portal/auth?" + urlencode(auth_params)
            
            logger.info(f"Generated TikTok Business auth URL for {auth_type}")
            
            return {
                "success": True,
                "data": {
                    "authUrl": auth_url,
                    "state": state,
                    "auth_type": auth_type
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_auth_callback(
        self, 
        auth_code: str, 
        state: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """Handle TikTok for Business OAuth callback"""
        try:
            # Exchange authorization code for access token
            token_data = await self._exchange_code_for_token(auth_code)
            
            # Get account info based on token type
            account_info = await self._get_account_info(token_data["access_token"])
            
            # Store or update account in database
            stmt = select(TikTokAccount).where(TikTokAccount.user_id == user_id)
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                account = TikTokAccount(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    tiktok_user_id=account_info.get("user_id", account_info.get("advertiser_id")),
                    username=account_info.get("display_name", ""),
                    display_name=account_info.get("display_name", ""),
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    access_token_expire_in=token_data.get("expires_in", 86400),
                    scopes=token_data.get("scope", "").split(","),
                    is_active=True,
                    connected_at=datetime.utcnow()
                )
                self.db.add(account)
            else:
                account.access_token = token_data["access_token"]
                account.refresh_token = token_data.get("refresh_token", account.refresh_token)
                account.access_token_expire_in = token_data.get("expires_in", 86400)
                account.is_active = True
                account.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            return {
                "success": True,
                "data": {
                    "status": "active",
                    "account_type": account_info.get("account_type", "user"),
                    "display_name": account_info.get("display_name"),
                    "connected_at": account.connected_at.isoformat()
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error handling auth callback: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _exchange_code_for_token(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            token_url = f"{self.auth_base_url}/open_api/v1.3/oauth2/access_token/"
            
            data = {
                "app_id": self.app_id,
                "auth_code": auth_code,
                "grant_type": "authorization_code"
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            try:
                response = await client.post(token_url, json=data, headers=headers)
                response_data = response.json()
                
                if response.status_code != 200 or response_data.get("code") != 0:
                    error_msg = response_data.get("message", "Unknown error")
                    logger.error(f"Token exchange failed: {error_msg}")
                    raise Exception(f"Token exchange failed: {error_msg}")
                
                return response_data.get("data", {})
                
            except httpx.RequestError as e:
                logger.error(f"HTTP request error: {str(e)}")
                raise Exception(f"Network error: {str(e)}")
    
    async def _get_account_info(self, access_token: str) -> Dict[str, Any]:
        """Get account information using access token"""
        async with httpx.AsyncClient() as client:
            # Try user info endpoint first
            user_info_url = f"{self.auth_base_url}/open_api/v1.3/user/info/"
            
            headers = {
                "Access-Token": access_token,
                "Content-Type": "application/json"
            }
            
            try:
                response = await client.get(user_info_url, headers=headers)
                response_data = response.json()
                
                if response.status_code == 200 and response_data.get("code") == 0:
                    user_data = response_data.get("data", {})
                    return {
                        "account_type": "user",
                        "user_id": user_data.get("open_id"),
                        "display_name": user_data.get("display_name"),
                        "avatar_url": user_data.get("avatar_url")
                    }
                
                # If user info fails, try advertiser info (for business accounts)
                advertiser_info_url = f"{self.auth_base_url}/open_api/v1.3/advertiser/info/"
                response = await client.get(advertiser_info_url, headers=headers)
                response_data = response.json()
                
                if response.status_code == 200 and response_data.get("code") == 0:
                    advertiser_data = response_data.get("data", {}).get("list", [{}])[0]
                    return {
                        "account_type": "business",
                        "advertiser_id": advertiser_data.get("advertiser_id"),
                        "display_name": advertiser_data.get("advertiser_name"),
                        "company": advertiser_data.get("company")
                    }
                
                raise Exception("Failed to get account info")
                
            except Exception as e:
                logger.error(f"Error getting account info: {str(e)}")
                raise

# Updated endpoint for TikTok Business authentication
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()

@router.post("/auth/init")
async def init_tiktok_business_auth(
    user_id: str = Query(...),
    redirect_uri: str = Query(...),
    auth_type: str = Query("USER_AUTH", regex="^(USER_AUTH|BUSINESS_AUTH)$"),
    db: AsyncSession = Depends(get_async_db)
):
    """Initialize TikTok for Business authentication"""
    try:
        service = TikTokBusinessAuthService(db)
        auth_data = await service.get_auth_url(
            user_id=user_id,
            redirect_uri=redirect_uri,
            auth_type=auth_type
        )
        
        if not auth_data["success"]:
            raise HTTPException(status_code=400, detail=auth_data.get("error"))
        
        return auth_data
        
    except Exception as e:
        logger.error(f"Error initializing auth: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/callback")
async def handle_tiktok_business_callback(
    auth_code: str = Query(..., alias="code"),
    state: str = Query(...),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_async_db)
):
    """Handle TikTok for Business OAuth callback"""
    try:
        service = TikTokBusinessAuthService(db)
        result = await service.handle_auth_callback(
            auth_code=auth_code,
            state=state,
            user_id=user_id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling callback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))