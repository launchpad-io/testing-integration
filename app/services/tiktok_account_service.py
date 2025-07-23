# app/services/tiktok_account_service.py - Updated with PKCE support
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.tiktok_models import TikTokAccount
from app.core.config import settings
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import httpx
import hashlib
import base64
import secrets

class TikTokAccountService:
    def __init__(self, db: AsyncSession):  # Changed to AsyncSession
        self.db = db
        self.client_id = settings.TIKTOK_CLIENT_ID
        self.client_secret = settings.TIKTOK_CLIENT_SECRET
        self.redirect_uri = settings.TIKTOK_REDIRECT_URI
        self.api_base_url = "https://open.tiktokapis.com/v2"
    
    def _generate_code_verifier(self) -> str:
        """Generate code verifier for PKCE"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    def _generate_code_challenge(self, code_verifier: str) -> str:
        """Generate code challenge from verifier using SHA256"""
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    async def get_connection_status(self, user_id: str) -> Dict[str, Any]:
        """Get TikTok connection status for a user"""
        try:
            # Use async select instead of sync query
            stmt = select(TikTokAccount).where(TikTokAccount.user_id == user_id)
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
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
            
            return {
                "success": True,
                "data": {
                    "status": "active" if account.is_active else "error",
                    "username": account.username,
                    "userId": account.tiktok_user_id,
                    "connectedAt": account.connected_at.isoformat() if account.connected_at else None,
                    "lastSync": account.last_sync_at.isoformat() if account.last_sync_at else None,
                    "error": None
                }
            }
        except Exception as e:
            print(f"Database error in get_connection_status: {e}")
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
    
    async def init_auth(self, user_id: str, redirect_uri: str, code_challenge: str, code_challenge_method: str, state: str) -> Dict[str, Any]:
        """Initialize TikTok OAuth authentication with PKCE"""
        
        # Build TikTok OAuth URL with PKCE parameters
        auth_params = {
            "client_key": self.client_id,
            "scope": "user.info.basic,video.list",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }
        
        # Create query string
        from urllib.parse import urlencode
        query_string = urlencode(auth_params)
        auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{query_string}"
        
        return {
            "success": True,
            "data": {
                "authUrl": auth_url,
                "state": state
            }
        }
    
    async def handle_auth_callback(self, code: str, state: str, user_id: str, code_verifier: str) -> Dict[str, Any]:
        """Handle TikTok OAuth callback with PKCE verification"""
        try:
            # Exchange code for access token with PKCE
            token_data = await self._exchange_code_for_token(code, code_verifier)
            
            # Get user info
            user_info = await self._get_user_info(token_data["access_token"])
            
            # Check if account exists using async select
            stmt = select(TikTokAccount).where(TikTokAccount.user_id == user_id)
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                account = TikTokAccount(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    tiktok_user_id=user_info["open_id"],
                    username=user_info.get("username", ""),
                    display_name=user_info.get("display_name", ""),
                    avatar_url=user_info.get("avatar_url", ""),
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    access_token_expire_in=token_data["expires_in"],
                    refresh_token_expire_in=token_data["refresh_expires_in"],
                    is_active=True,
                    connected_at=datetime.utcnow()
                )
                self.db.add(account)
            else:
                account.tiktok_user_id = user_info["open_id"]
                account.username = user_info.get("username", "")
                account.display_name = user_info.get("display_name", "")
                account.avatar_url = user_info.get("avatar_url", "")
                account.access_token = token_data["access_token"]
                account.refresh_token = token_data["refresh_token"]
                account.access_token_expire_in = token_data["expires_in"]
                account.refresh_token_expire_in = token_data["refresh_expires_in"]
                account.is_active = True
                account.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            return {
                "success": True,
                "data": {
                    "status": "active",
                    "username": user_info.get("username"),
                    "userId": user_info["open_id"],
                    "connectedAt": account.connected_at.isoformat() if account.connected_at else datetime.utcnow().isoformat(),
                    "lastSync": "Just now"
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "status": "error",
                    "username": None,
                    "userId": None,
                    "connectedAt": None,
                    "lastSync": None,
                    "error": str(e)
                }
            }
    
    async def disconnect_account(self, user_id: str) -> Dict[str, Any]:
        """Disconnect TikTok account"""
        try:
            stmt = select(TikTokAccount).where(TikTokAccount.user_id == user_id)
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if account:
                account.is_active = False
                account.access_token = None
                account.refresh_token = None
                await self.db.commit()
            
            return {"success": True}
        except Exception as e:
            await self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def sync_account_data(self, user_id: str) -> Dict[str, Any]:
        """Sync TikTok account data"""
        try:
            stmt = select(TikTokAccount).where(
                TikTokAccount.user_id == user_id,
                TikTokAccount.is_active == True
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                return {
                    "success": False,
                    "error": "TikTok account not connected"
                }
            
            # Refresh token if needed
            if self._is_token_expired(account):
                await self._refresh_token(account)
            
            # Get updated user info
            user_info = await self._get_user_info(account.access_token)
            
            # Update account data
            account.username = user_info.get("username", account.username)
            account.display_name = user_info.get("display_name", account.display_name)
            account.avatar_url = user_info.get("avatar_url", account.avatar_url)
            account.follower_count = user_info.get("follower_count", account.follower_count)
            account.following_count = user_info.get("following_count", account.following_count)
            account.like_count = user_info.get("like_count", account.like_count)
            account.video_count = user_info.get("video_count", account.video_count)
            account.last_sync_at = datetime.utcnow()
            
            await self.db.commit()
            return {"success": True}
            
        except Exception as e:
            await self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_account_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get TikTok account metrics"""
        try:
            stmt = select(TikTokAccount).where(
                TikTokAccount.user_id == user_id,
                TikTokAccount.is_active == True
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                return {
                    "success": False,
                    "error": "TikTok account not connected"
                }
            
            return {
                "success": True,
                "data": {
                    "followers": account.follower_count or 0,
                    "following": account.following_count or 0,
                    "likes": account.like_count or 0,
                    "videos": account.video_count or 0,
                    "lastUpdated": account.last_sync_at.isoformat() if account.last_sync_at else None
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # Existing HTTP helper methods remain mostly unchanged, but now commit/rollback are awaited
    async def _exchange_code_for_token(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for access token with PKCE"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": code_verifier  # PKCE parameter
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Token exchange failed: {response.text}")
            
            result = response.json()
            
            if not result.get("data"):
                raise Exception(f"Token exchange failed: {result.get('message', 'Unknown error')}")
            
            return result["data"]
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get TikTok user information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/user/info/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get user info: {response.text}")
            
            result = response.json()
            
            if not result.get("data", {}).get("user"):
                raise Exception(f"Failed to get user info: {result.get('message', 'Unknown error')}")
            
            return result["data"]["user"]
    
    async def _refresh_token(self, account: TikTokAccount) -> bool:
        """Refresh access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://open.tiktokapis.com/v2/oauth/token/",
                    data={
                        "client_key": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": account.refresh_token
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code != 200:
                    return False
                
                result = response.json()
                
                if not result.get("data"):
                    return False
                
                token_data = result["data"]
                
                account.access_token = token_data["access_token"]
                account.refresh_token = token_data["refresh_token"]
                account.access_token_expire_in = token_data["expires_in"]
                account.refresh_token_expire_in = token_data["refresh_expires_in"]
                
                await self.db.commit()
                return True
                
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return False
    
    def _is_token_expired(self, account: TikTokAccount) -> bool:
        """Check if access token is expired"""
        if not account.access_token_expire_in or not account.updated_at:
            return True
        
        # Add some buffer time (5 minutes)
        buffer_time = timedelta(minutes=5)
        expiry_time = account.updated_at + timedelta(seconds=account.access_token_expire_in) - buffer_time
        
        return datetime.utcnow() > expiry_time