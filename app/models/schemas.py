# app/models/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# Auth schemas
class AuthorizationRequest(BaseModel):
    redirect_uri: str
    state: Optional[str] = None

class TokenExchangeRequest(BaseModel):
    auth_code: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_token_expire_in: int
    refresh_token_expire_in: int
    shop_id: str
    shop_name: str

# Shop schemas
class ShopInfo(BaseModel):
    shop_id: str
    shop_name: str
    shop_code: str
    shop_cipher: str
    is_active: bool

class ShopListResponse(BaseModel):
    shops: List[ShopInfo]
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    total: Optional[int] = 0

# Product schemas
class ProductSku(BaseModel):
    id: str
    seller_sku: str
    price: Dict[str, Any]
    stock_info: Dict[str, Any]

class ProductBase(BaseModel):
    product_id: str
    product_name: str
    product_status: int
    category_id: str
    brand_id: Optional[str] = None
    images: List[str]
    skus: List[ProductSku]
    shop_id: Optional[str] = None  # Added for security validation

class ProductSearchRequest(BaseModel):
    page_size: int = Field(default=20, le=100)
    page_number: int = Field(default=1, ge=1)
    search_title: Optional[str] = None
    product_status: Optional[int] = None
    create_time_from: Optional[int] = None
    create_time_to: Optional[int] = None

class ProductListResponse(BaseModel):
    total: int
    products: List[ProductBase]
    has_more: bool
    search_params: Optional[Dict[str, Any]] = None
    cached: Optional[bool] = False

# Order schemas
class OrderLineItem(BaseModel):
    item_id: str
    product_id: str
    product_name: str
    sku_id: str
    sku_name: str
    quantity: int
    sale_price: float
    seller_discount: float
    platform_discount: float

class OrderBase(BaseModel):
    order_id: str
    order_status: int
    payment_status: str
    fulfillment_type: int
    create_time: int
    update_time: int
    line_items: List[OrderLineItem]
    payment_info: Dict[str, Any]
    recipient_address: Dict[str, Any]
    shop_id: Optional[str] = None  # Added for security validation

class OrderSearchRequest(BaseModel):
    page_size: int = Field(default=20, le=100)
    page_number: int = Field(default=1, ge=1)
    order_status: Optional[int] = None
    create_time_from: Optional[int] = None
    create_time_to: Optional[int] = None
    update_time_from: Optional[int] = None
    update_time_to: Optional[int] = None

class OrderListResponse(BaseModel):
    total: int
    orders: List[OrderBase]
    has_more: bool

# Webhook schemas
class WebhookEvent(BaseModel):
    shop_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: int

# Additional schemas for enhanced endpoints
class OrderBatchSyncRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=90)
    sync_mode: str = Field(default="recent", pattern="^(recent|all|changes_only)$")

class ProductBulkUpdateRequest(BaseModel):
    products: List[Dict[str, Any]]
    update_fields: List[str] = Field(default=["price", "inventory"])

class ProductImportRequest(BaseModel):
    file_url: str
    file_format: str = Field(..., pattern="^(csv|xlsx)$")
    mapping: Optional[Dict[str, str]] = None

class SyncStatus(BaseModel):
    sync_id: str
    status: str
    progress: int
    total_items: int
    processed_items: int
    failed_items: int
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    errors: List[Dict[str, Any]] = []

# Error response schemas
class ErrorResponse(BaseModel):
    detail: str
    type: Optional[str] = "error"
    code: Optional[str] = None

class ValidationErrorResponse(BaseModel):
    detail: List[Dict[str, Any]]
    type: str = "validation_error"

# Pagination schemas
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

# Analytics schemas
class OrderAnalytics(BaseModel):
    shop_id: str
    date_range: Dict[str, str]
    total_orders: int
    total_revenue: float
    average_order_value: float
    status_breakdown: Dict[int, int]
    daily_orders: List[Dict[str, Any]]

class InventoryAnalytics(BaseModel):
    shop_id: str
    total_products: int
    total_skus: int
    low_stock_products: List[Dict[str, Any]]
    out_of_stock_products: List[Dict[str, Any]]
    inventory_value: float
    last_updated: datetime

# Batch operation schemas
class BatchOperationResult(BaseModel):
    success_count: int
    failed_count: int
    failed_items: Optional[List[Dict[str, Any]]] = []
    operation_id: Optional[str] = None

# Token refresh schema
class TokenRefreshRequest(BaseModel):
    refresh_token: str

# Shop update schema  
class ShopUpdateRequest(BaseModel):
    shop_name: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None