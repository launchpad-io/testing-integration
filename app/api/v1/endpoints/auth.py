# app/api/v1/endpoints/auth.py - Simplified version
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.schemas import (
    AuthorizationRequest,
    TokenExchangeRequest,
    TokenResponse,
    ShopListResponse
)
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_shop
from typing import Optional

router = APIRouter()

@router.post("/authorize", response_model=dict)
async def get_authorization_url(
    request: AuthorizationRequest,
    db: Session = Depends(get_db)
):
    """Generate TikTok Shop authorization URL"""
    auth_service = AuthService(db)
    auth_url = await auth_service.get_authorization_url(
        redirect_uri=request.redirect_uri,
        state=request.state
    )
    return {"auth_url": auth_url}

@router.post("/token/exchange", response_model=TokenResponse)
async def exchange_token(
    request: TokenExchangeRequest,
    db: Session = Depends(get_db)
):
    """Exchange authorization code for access token"""
    auth_service = AuthService(db)
    try:
        token_data = await auth_service.exchange_auth_code(request.auth_code)
        return token_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    shop_id: str,
    db: Session = Depends(get_db)
):
    """Refresh access token for a shop"""
    auth_service = AuthService(db)
    try:
        token_data = await auth_service.refresh_shop_token(shop_id)
        return token_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shops", response_model=ShopListResponse)
async def get_authorized_shops(
    db: Session = Depends(get_db)
):
    """Get list of authorized shops"""
    auth_service = AuthService(db)
    shops = await auth_service.get_all_shops()
    return {"shops": shops}