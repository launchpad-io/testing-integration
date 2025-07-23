
# app/core/dependencies.py
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.tiktok_models import TikTokShop
from typing import Optional

async def get_current_shop(
    x_shop_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> str:
    """Get current shop ID from header"""
    if not x_shop_id:
        raise HTTPException(
            status_code=400,
            detail="Shop ID header required"
        )
    
    # Verify shop exists
    shop = db.query(TikTokShop).filter(
        TikTokShop.shop_id == x_shop_id
    ).first()
    
    if not shop:
        raise HTTPException(
            status_code=404,
            detail="Shop not found"
        )
    
    if not shop.is_active:
        raise HTTPException(
            status_code=403,
            detail="Shop is not active"
        )
    
    return x_shop_id
