# app/api/v1/endpoints/products.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.schemas import (
    ProductSearchRequest,
    ProductListResponse,
    ProductBase,
    ProductBulkUpdateRequest,
    ProductImportRequest
)
from app.services.product_service import ProductService
from app.core.dependencies import get_current_shop
from app.core.rate_limiter import limiter
from app.core.cache import cache_manager
from typing import Optional, List
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/search", response_model=ProductListResponse)
@limiter.limit("100/minute")
async def search_products(
    request: Request,
    search_request: ProductSearchRequest,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db),
    use_cache: bool = Query(True, description="Use cached results if available")
):
    """Search products with filters and caching"""
    product_service = ProductService(db)
    
    # Validate search parameters
    if search_request.page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size cannot exceed 100"
        )
    
    # Generate cache key
    cache_key = f"products:search:{shop_id}:{hash(str(search_request.dict()))}"
    
    # Check cache if enabled
    if use_cache:
        cached_result = await cache_manager.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for product search - shop: {shop_id}")
            return ProductListResponse.parse_raw(cached_result)
    
    try:
        # Validate date range if provided
        if search_request.create_time_from and search_request.create_time_to:
            if search_request.create_time_from > search_request.create_time_to:
                raise HTTPException(
                    status_code=400,
                    detail="create_time_from must be before create_time_to"
                )
        
        # Search products with timeout
        result = await asyncio.wait_for(
            product_service.search_products(
                shop_id=shop_id,
                **search_request.dict(exclude_unset=True)
            ),
            timeout=30.0  # 30 second timeout
        )
        
        # Cache the result for 10 minutes
        if use_cache and result.products:
            await cache_manager.set(cache_key, result.json(), expire=600)
        
        # Add search metadata
        result.search_params = search_request.dict(exclude_unset=True)
        result.cached = False
        
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Product search timeout for shop {shop_id}")
        raise HTTPException(status_code=504, detail="Search request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product search error for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search products")

@router.get("/{product_id}", response_model=ProductBase)
@limiter.limit("200/minute")
async def get_product_detail(
    request: Request,
    product_id: str,
    shop_id: str = Depends(get_current_shop),
    include_inventory: bool = Query(False, description="Include real-time inventory"),
    db: Session = Depends(get_db)
):
    """Get product details with ownership validation"""
    product_service = ProductService(db)
    
    # Cache key for product details
    cache_key = f"product:detail:{shop_id}:{product_id}"
    
    # Check cache first (unless inventory is requested)
    if not include_inventory:
        cached_product = await cache_manager.get(cache_key)
        if cached_product:
            return ProductBase.parse_raw(cached_product)
    
    try:
        # Get product with ownership validation
        product = await product_service.get_product_detail_with_validation(
            shop_id, product_id, include_inventory
        )
        
        if not product:
            logger.warning(f"Product not found - shop: {shop_id}, product: {product_id}")
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Security check: Ensure product belongs to shop
        if product.shop_id != shop_id:
            logger.error(f"Unauthorized product access - shop: {shop_id}, product: {product_id}")
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Cache product details (without inventory data)
        if not include_inventory:
            await cache_manager.set(cache_key, product.json(), expire=1800)  # 30 minutes
        
        return product
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch product")

@router.post("/sync")
@limiter.limit("5/hour")
async def sync_products(
    request: Request,
    background_tasks: BackgroundTasks,
    sync_mode: str = Query("full", pattern="^(full|incremental|changes_only)$"),
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Sync products from TikTok Shop with different modes"""
    product_service = ProductService(db)
    
    try:
        # Check if sync is already in progress
        if await product_service.is_sync_in_progress(shop_id):
            raise HTTPException(
                status_code=429,
                detail="Product sync already in progress for this shop"
            )
        
        # Start sync based on mode
        if sync_mode == "full":
            sync_id = await product_service.start_full_sync(shop_id, background_tasks)
        elif sync_mode == "incremental":
            sync_id = await product_service.start_incremental_sync(shop_id, background_tasks)
        else:  # changes_only
            sync_id = await product_service.start_changes_sync(shop_id, background_tasks)
        
        # Clear product cache for this shop
        await cache_manager.delete_pattern(f"products:*:{shop_id}:*")
        await cache_manager.delete_pattern(f"product:*:{shop_id}:*")
        
        return {
            "message": f"Product {sync_mode} sync started",
            "sync_id": sync_id,
            "sync_mode": sync_mode,
            "status_endpoint": f"/api/v1/products/sync/status/{sync_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product sync error for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start product sync")

@router.get("/sync/status/{sync_id}")
async def get_sync_status(
    sync_id: str,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Get status of ongoing sync operation"""
    product_service = ProductService(db)
    
    try:
        status = await product_service.get_sync_status(shop_id, sync_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Sync operation not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sync status {sync_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sync status")

@router.put("/batch/update")
@limiter.limit("20/minute")
async def batch_update_products(
    request: Request,
    update_request: ProductBulkUpdateRequest,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Batch update product information"""
    product_service = ProductService(db)
    
    try:
        # Validate batch size
        if len(update_request.products) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 products can be updated at once"
            )
        
        # Extract product IDs
        product_ids = [p.product_id for p in update_request.products]
        
        # Validate all products belong to the shop
        valid_products = await product_service.validate_product_ownership_batch(
            shop_id, product_ids
        )
        
        if len(valid_products) != len(product_ids):
            invalid_ids = set(product_ids) - set(valid_products)
            raise HTTPException(
                status_code=403,
                detail=f"Products not found or don't belong to shop: {invalid_ids}"
            )
        
        # Perform batch update
        updated_count = await product_service.batch_update_products(
            shop_id, update_request.products
        )
        
        # Clear cache for updated products
        for product_id in product_ids:
            await cache_manager.delete(f"product:detail:{shop_id}:{product_id}")
        
        return {
            "updated_count": updated_count,
            "product_ids": product_ids,
            "cache_cleared": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update products")

@router.post("/import")
@limiter.limit("2/hour")
async def import_products(
    request: Request,
    import_request: ProductImportRequest,
    background_tasks: BackgroundTasks,
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Import products from CSV or Excel file"""
    product_service = ProductService(db)
    
    try:
        # Validate file format
        if import_request.file_format not in ["csv", "xlsx"]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Use CSV or XLSX"
            )
        
        # Start import process in background
        import_id = await product_service.start_product_import(
            shop_id=shop_id,
            file_url=import_request.file_url,
            file_format=import_request.file_format,
            background_tasks=background_tasks
        )
        
        return {
            "message": "Product import started",
            "import_id": import_id,
            "status_endpoint": f"/api/v1/products/import/status/{import_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product import error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start product import")

@router.get("/analytics/inventory")
@limiter.limit("30/minute")
async def get_inventory_analytics(
    request: Request,
    low_stock_threshold: int = Query(10, description="Threshold for low stock alert"),
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
):
    """Get inventory analytics and alerts"""
    product_service = ProductService(db)
    
    try:
        analytics = await product_service.get_inventory_analytics(
            shop_id, low_stock_threshold
        )
        
        return analytics
        
    except Exception as e:
        logger.error(f"Inventory analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate inventory analytics")