# app/api/v1/endpoints/shops.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.tiktok_models import TikTokShop
from app.models.schemas import ShopListResponse, ShopInfo
from typing import List

router = APIRouter()

@router.get("/", response_model=ShopListResponse)
async def get_shops(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get all shops with pagination"""
    shops = db.query(TikTokShop).offset(skip).limit(limit).all()
    total = db.query(TikTokShop).count()
    
    shop_list = [
        ShopInfo(
            shop_id=shop.shop_id,
            shop_name=shop.shop_name,
            shop_code=shop.shop_code,
            shop_cipher=shop.shop_cipher,
            is_active=shop.is_active
        )
        for shop in shops
    ]
    
    return {
        "shops": shop_list,
        "page": (skip // limit) + 1,
        "page_size": limit,
        "total": total
    }

@router.get("/{shop_id}")
async def get_shop_details(
    shop_id: str,
    db: Session = Depends(get_db)
):
    """Get specific shop details"""
    shop = db.query(TikTokShop).filter(TikTokShop.shop_id == shop_id).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    return {
        "shop_id": shop.shop_id,
        "shop_name": shop.shop_name,
        "shop_code": shop.shop_code,
        "is_active": shop.is_active,
        "created_at": shop.created_at,
        "last_sync": getattr(shop, 'last_sync_at', None)
    }