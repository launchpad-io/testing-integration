
# app/services/product_service.py
from sqlalchemy.orm import Session
from app.services.tiktok_client import TikTokShopClient
from app.models.tiktok_models import TikTokShop, TikTokProduct
from app.models.schemas import ProductListResponse, ProductBase
from typing import Dict, Any, List
import uuid
import json

class ProductService:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_shop_token(self, shop_id: str) -> str:
        """Get access token for shop"""
        shop = self.db.query(TikTokShop).filter(
            TikTokShop.shop_id == shop_id
        ).first()
        
        if not shop:
            raise ValueError("Shop not found")
        
        return shop.access_token
    
    async def search_products(self, shop_id: str, **kwargs) -> ProductListResponse:
        """Search products from TikTok Shop"""
        access_token = self._get_shop_token(shop_id)
        
        async with TikTokShopClient() as client:
            response = await client.search_products(
                access_token=access_token,
                shop_id=shop_id,
                **kwargs
            )
            
            data = response.get("data", {})
            products = []
            
            for product_data in data.get("products", []):
                # Save or update product in database
                product = self.db.query(TikTokProduct).filter(
                    TikTokProduct.product_id == product_data["product_id"]
                ).first()
                
                if not product:
                    product = TikTokProduct(
                        id=str(uuid.uuid4()),
                        shop_id=shop_id,
                        product_id=product_data["product_id"]
                    )
                    self.db.add(product)
                
                # Update product data
                product.product_name = product_data["product_name"]
                product.product_status = product_data["product_status"]
                product.category_id = product_data.get("category_id")
                product.brand_id = product_data.get("brand_id")
                product.skus = product_data.get("skus", [])
                product.images = product_data.get("images", [])
                product.create_time = product_data.get("create_time")
                product.update_time = product_data.get("update_time")
                
                products.append(ProductBase(**product_data))
            
            self.db.commit()
            
            return ProductListResponse(
                total=data.get("total_count", 0),
                products=products,
                has_more=data.get("has_more", False)
            )
    
    async def get_product_detail(self, shop_id: str, product_id: str) -> ProductBase:
        """Get product details from TikTok Shop"""
        access_token = self._get_shop_token(shop_id)
        
        async with TikTokShopClient() as client:
            response = await client.get_product_detail(
                access_token=access_token,
                shop_id=shop_id,
                product_id=product_id
            )
            
            data = response.get("data", {})
            
            if not data:
                return None
            
            # Update product in database
            product = self.db.query(TikTokProduct).filter(
                TikTokProduct.product_id == product_id
            ).first()
            
            if product:
                product.product_name = data["product_name"]
                product.product_status = data["product_status"]
                product.category_id = data.get("category_id")
                product.brand_id = data.get("brand_id")
                product.skus = data.get("skus", [])
                product.images = data.get("images", [])
                product.update_time = data.get("update_time")
                self.db.commit()
            
            return ProductBase(**data)
    
    async def sync_all_products(self, shop_id: str) -> int:
        """Sync all products from TikTok Shop"""
        total_synced = 0
        page_number = 1
        has_more = True
        
        while has_more:
            result = await self.search_products(
                shop_id=shop_id,
                page_size=100,
                page_number=page_number
            )
            
            total_synced += len(result.products)
            has_more = result.has_more
            page_number += 1
        
        return total_synced
