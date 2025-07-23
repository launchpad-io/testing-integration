# app/services/auth_service.py - Simplified version
from sqlalchemy.orm import Session
from app.services.tiktok_client import TikTokShopClient
from app.models.tiktok_models import TikTokShop
from app.models.schemas import TokenResponse, ShopInfo
from typing import List, Optional
import uuid
from datetime import datetime

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Generate TikTok Shop authorization URL"""
        if not state:
            state = str(uuid.uuid4())
            
        async with TikTokShopClient() as client:
            return await client.get_auth_url(state, redirect_uri)
    
    async def exchange_auth_code(self, auth_code: str) -> TokenResponse:
        """Exchange authorization code for access token"""
        async with TikTokShopClient() as client:
            token_data = await client.get_access_token(auth_code)
            
            # Extract data from response
            data = token_data.get("data", {})
            
            # Save or update shop in database
            shop = self.db.query(TikTokShop).filter(
                TikTokShop.shop_id == data["seller_base_info"]["shop_id"]
            ).first()
            
            if not shop:
                shop = TikTokShop(
                    id=str(uuid.uuid4()),
                    shop_id=data["seller_base_info"]["shop_id"],
                    shop_name=data["seller_base_info"]["shop_name"],
                    shop_code=data["seller_base_info"]["shop_code"],
                    shop_cipher=data["seller_base_info"]["shop_cipher"],
                )
                self.db.add(shop)
            
            # Update tokens
            shop.access_token = data["access_token"]
            shop.refresh_token = data["refresh_token"]
            shop.access_token_expire_in = data["access_token_expire_in"]
            shop.refresh_token_expire_in = data["refresh_token_expire_in"]
            shop.is_active = True
            
            self.db.commit()
            
            return TokenResponse(
                access_token=shop.access_token,
                refresh_token=shop.refresh_token,
                access_token_expire_in=shop.access_token_expire_in,
                refresh_token_expire_in=shop.refresh_token_expire_in,
                shop_id=shop.shop_id,
                shop_name=shop.shop_name
            )
    
    async def refresh_shop_token(self, shop_id: str) -> TokenResponse:
        """Refresh access token for a shop"""
        shop = self.db.query(TikTokShop).filter(
            TikTokShop.shop_id == shop_id
        ).first()
        
        if not shop:
            raise ValueError("Shop not found")
        
        async with TikTokShopClient() as client:
            token_data = await client.refresh_access_token(shop.refresh_token)
            
            data = token_data.get("data", {})
            
            # Update tokens
            shop.access_token = data["access_token"]
            shop.refresh_token = data["refresh_token"]
            shop.access_token_expire_in = data["access_token_expire_in"]
            shop.refresh_token_expire_in = data["refresh_token_expire_in"]
            
            self.db.commit()
            
            return TokenResponse(
                access_token=shop.access_token,
                refresh_token=shop.refresh_token,
                access_token_expire_in=shop.access_token_expire_in,
                refresh_token_expire_in=shop.refresh_token_expire_in,
                shop_id=shop.shop_id,
                shop_name=shop.shop_name
            )
    
    async def get_all_shops(self) -> List[ShopInfo]:
        """Get all authorized shops"""
        shops = self.db.query(TikTokShop).filter(
            TikTokShop.is_active == True
        ).all()
        
        return [
            ShopInfo(
                shop_id=shop.shop_id,
                shop_name=shop.shop_name,
                shop_code=shop.shop_code,
                shop_cipher=shop.shop_cipher,
                is_active=shop.is_active
            )
            for shop in shops
        ]