# app/api/v1/endpoints/orders.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.schemas import (
    OrderSearchRequest,
    OrderListResponse,
    OrderBase,
    OrderBatchSyncRequest
)
from app.services.order_service import OrderService
from app.core.dependencies import get_current_shop
from app.core.rate_limiter import limiter
from app.core.cache import cache_manager
from typing import List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/search", response_model=OrderListResponse)
@limiter.limit("60/minute")
async def search_orders(
    request: Request,
    search_request: OrderSearchRequest,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Search orders with filters and caching"""
    order_service = OrderService(db)
    
    # Generate cache key
    cache_key = f"orders:search:{shop_id}:{search_request.dict()}"
    
    # Check cache first
    cached_result = await cache_manager.get(cache_key)
    if cached_result:
        logger.info(f"Cache hit for order search - shop: {shop_id}")
        return OrderListResponse.parse_raw(cached_result)
    
    try:
        # Validate date range
        if search_request.create_time_from and search_request.create_time_to:
            if search_request.create_time_from > search_request.create_time_to:
                raise HTTPException(
                    status_code=400,
                    detail="create_time_from must be before create_time_to"
                )
        
        result = await order_service.search_orders(
            shop_id=shop_id,
            **search_request.dict(exclude_unset=True)
        )
        
        # Cache the result for 5 minutes
        await cache_manager.set(cache_key, result.json(), expire=300)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order search error for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search orders")

@router.get("/{order_id}", response_model=OrderBase)
@limiter.limit("120/minute")
async def get_order_detail(
    request: Request,
    order_id: str,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Get order details with ownership validation"""
    order_service = OrderService(db)
    
    try:
        # SECURITY FIX: Validate order belongs to the shop
        order = await order_service.get_order_detail_with_validation(shop_id, order_id)
        
        if not order:
            logger.warning(f"Order not found or unauthorized - shop: {shop_id}, order: {order_id}")
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Additional security check
        if order.shop_id != shop_id:
            logger.error(f"Unauthorized order access attempt - shop: {shop_id}, order: {order_id}")
            raise HTTPException(status_code=403, detail="Forbidden")
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch order")

@router.post("/sync")
@limiter.limit("5/hour")  # Limit sync operations
async def sync_orders(
    request: Request,
    sync_request: Optional[OrderBatchSyncRequest] = None,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Sync recent orders from TikTok Shop with rate limiting"""
    order_service = OrderService(db)
    
    try:
        # Check if sync is already in progress
        if await order_service.is_sync_in_progress(shop_id):
            raise HTTPException(
                status_code=429,
                detail="Sync already in progress for this shop"
            )
        
        # Default to last 7 days if not specified
        days = sync_request.days if sync_request else 7
        
        # Validate days range
        if days < 1 or days > 90:
            raise HTTPException(
                status_code=400,
                detail="Sync period must be between 1 and 90 days"
            )
        
        # Start sync with progress tracking
        sync_id = await order_service.start_sync_with_progress(shop_id, days)
        
        return {
            "message": "Order sync started",
            "sync_id": sync_id,
            "estimated_time": f"{days * 2} seconds",
            "status_endpoint": f"/api/v1/orders/sync/status/{sync_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order sync error for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start order sync")

@router.get("/sync/status/{sync_id}")
async def get_sync_status(
    sync_id: str,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Get status of ongoing sync operation"""
    order_service = OrderService(db)
    
    try:
        status = await order_service.get_sync_status(shop_id, sync_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Sync operation not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sync status {sync_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sync status")

@router.post("/batch/update-status")
@limiter.limit("20/minute")
async def batch_update_order_status(
    request: Request,
    order_ids: List[str],
    new_status: int,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Batch update order status with validation"""
    order_service = OrderService(db)
    
    try:
        # Validate batch size
        if len(order_ids) > 100:
            raise HTTPException(
                status_code=400,
                detail="Maximum 100 orders can be updated at once"
            )
        
        # Validate all orders belong to the shop
        valid_orders = await order_service.validate_order_ownership_batch(
            shop_id, order_ids
        )
        
        if len(valid_orders) != len(order_ids):
            raise HTTPException(
                status_code=403,
                detail=f"Some orders don't belong to shop {shop_id}"
            )
        
        # Perform batch update
        updated_count = await order_service.batch_update_status(
            shop_id, order_ids, new_status
        )
        
        return {
            "updated_count": updated_count,
            "order_ids": order_ids,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update orders")

@router.get("/analytics/summary")
@limiter.limit("30/minute")
async def get_order_analytics(
    request: Request,
    start_date: str = Query(..., pattern="^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., pattern="^\d{4}-\d{2}-\d{2}$"),
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Get order analytics summary"""
    order_service = OrderService(db)
    
    try:
        analytics = await order_service.get_order_analytics(
            shop_id, start_date, end_date
        )
        
        return analytics
        
    except Exception as e:
        logger.error(f"Analytics error for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate analytics")