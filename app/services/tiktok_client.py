# app/services/tiktok_client.py
import httpx
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.utils.signature import TikTokSignature
import json
import logging

logger = logging.getLogger(__name__)

class TikTokShopClient:
    """Client for interacting with TikTok Shop Partner API"""
    
    def __init__(self):
        self.app_key = settings.TIKTOK_APP_KEY
        self.app_secret = settings.TIKTOK_APP_SECRET
        self.base_url = settings.TIKTOK_API_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
        shop_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to TikTok Shop API"""
        
        # Prepare parameters with signature
        request_params = TikTokSignature.prepare_request_params(
            app_key=self.app_key,
            app_secret=self.app_secret,
            path=path,
            params=params,
            access_token=access_token,
            shop_id=shop_id
        )
        
        url = f"{self.base_url}{path}"
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=request_params)
            elif method == "POST":
                # For POST requests, params go in URL, data in body
                response = await self.client.post(
                    url,
                    params=request_params,
                    json=data
                )
            elif method == "PUT":
                response = await self.client.put(
                    url,
                    params=request_params,
                    json=data
                )
            elif method == "DELETE":
                response = await self.client.delete(url, params=request_params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error making request to TikTok API: {str(e)}")
            raise
    
    # Authentication methods
    async def get_auth_url(self, state: str, redirect_uri: str) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "app_key": self.app_key,
            "state": state,
            "redirect_uri": redirect_uri,
        }
        return f"{settings.TIKTOK_AUTH_URL}?{httpx.QueryParams(params)}"
    
    async def get_access_token(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        path = "/api/v2/token/get"
        params = {
            "auth_code": auth_code,
            "grant_type": "authorized_code"
        }
        return await self._make_request("GET", path, params=params)
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        path = "/api/v2/token/refresh"
        params = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        return await self._make_request("GET", path, params=params)
    
    # Shop methods
    async def get_authorized_shops(self, access_token: str) -> Dict[str, Any]:
        """Get list of authorized shops"""
        path = "/api/shop/get_authorized_shop"
        return await self._make_request("GET", path, access_token=access_token)
    
    # Product methods
    async def search_products(
        self,
        access_token: str,
        shop_id: str,
        page_size: int = 20,
        page_number: int = 1,
        **filters
    ) -> Dict[str, Any]:
        """Search products with filters"""
        path = "/api/products/search"
        params = {
            "page_size": page_size,
            "page_number": page_number,
            **filters
        }
        return await self._make_request(
            "POST", 
            path, 
            params=params,
            access_token=access_token,
            shop_id=shop_id
        )
    
    async def get_product_detail(
        self,
        access_token: str,
        shop_id: str,
        product_id: str
    ) -> Dict[str, Any]:
        """Get product details"""
        path = "/api/products/details"
        params = {"product_id": product_id}
        return await self._make_request(
            "GET",
            path,
            params=params,
            access_token=access_token,
            shop_id=shop_id
        )
    
    # Order methods
    async def get_order_list(
        self,
        access_token: str,
        shop_id: str,
        page_size: int = 20,
        page_number: int = 1,
        **filters
    ) -> Dict[str, Any]:
        """Get order list with filters"""
        path = "/api/orders/search"
        params = {
            "page_size": page_size,
            "page_number": page_number,
            **filters
        }
        return await self._make_request(
            "POST",
            path,
            params=params,
            access_token=access_token,
            shop_id=shop_id
        )
    
    async def get_order_detail(
        self,
        access_token: str,
        shop_id: str,
        order_ids: List[str]
    ) -> Dict[str, Any]:
        """Get order details"""
        path = "/api/orders/detail/query"
        data = {"order_id_list": order_ids}
        return await self._make_request(
            "POST",
            path,
            data=data,
            access_token=access_token,
            shop_id=shop_id
        )
    
    # Webhook methods
    async def verify_webhook(self, signature: str, body: bytes) -> bool:
        """Verify webhook signature"""
        expected_signature = hmac.new(
            self.app_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)