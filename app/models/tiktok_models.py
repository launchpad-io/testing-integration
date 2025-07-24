# app/models/tiktok_models.py - Enhanced with video tracking
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, ForeignKey, BigInteger, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.database import Base

class TikTokShop(Base):
    __tablename__ = "tiktok_shops"
    
    id = Column(String, primary_key=True)
    shop_id = Column(String, unique=True, index=True)
    shop_name = Column(String)
    shop_code = Column(String)
    shop_cipher = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    access_token_expire_in = Column(Integer)
    refresh_token_expire_in = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    products = relationship("TikTokProduct", back_populates="shop")
    orders = relationship("TikTokOrder", back_populates="shop")

class TikTokAccount(Base):
    __tablename__ = "tiktok_accounts"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)  # Link to our user system
    tiktok_user_id = Column(String, unique=True, index=True)
    username = Column(String)
    display_name = Column(String)
    avatar_url = Column(String)
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    
    # OAuth tokens
    access_token = Column(String)
    refresh_token = Column(String)
    access_token_expire_in = Column(Integer)
    refresh_token_expire_in = Column(Integer)
    
    # Connection status
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    videos = relationship("TikTokVideo", back_populates="account")

class TikTokVideo(Base):
    __tablename__ = "tiktok_videos"
    
    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("tiktok_accounts.id"))
    video_id = Column(String, unique=True, index=True)
    title = Column(Text)
    description = Column(Text)
    
    # Video metrics
    view_count = Column(BigInteger, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    play_count = Column(BigInteger, default=0)
    
    # Video metadata
    duration = Column(Integer)  # in seconds
    video_url = Column(String)
    share_url = Column(String)
    cover_image_url = Column(String)
    dynamic_cover_url = Column(String)
    
    # Video status
    video_status = Column(String, default="public")  # public, private, deleted
    is_deleted = Column(Boolean, default=False)
    
    # Campaign tracking
    campaign_id = Column(String, index=True)  # Link to campaign if this is a deliverable
    is_deliverable = Column(Boolean, default=False)
    deliverable_id = Column(String, index=True)  # Link to specific deliverable
    deliverable_status = Column(String, default="pending")  # pending, approved, rejected
    
    # Attribution tracking
    attributed_gmv = Column(Numeric(12, 2), default=0.00)
    attributed_orders = Column(Integer, default=0)
    last_attribution_update = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True))  # When video was posted on TikTok
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())  # When we found it
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    account = relationship("TikTokAccount", back_populates="videos")
    metrics_history = relationship("TikTokVideoMetrics", back_populates="video")
    attributed_orders = relationship("TikTokOrder", back_populates="attributed_video")

class TikTokVideoMetrics(Base):
    __tablename__ = "tiktok_video_metrics"
    
    id = Column(String, primary_key=True)
    video_id = Column(String, ForeignKey("tiktok_videos.video_id"))
    
    # Snapshot metrics
    view_count = Column(BigInteger, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    play_count = Column(BigInteger, default=0)
    
    # Calculated metrics
    engagement_rate = Column(Numeric(5, 2), default=0.00)
    view_velocity = Column(Integer, default=0)  # Views per hour since last check
    
    # Timestamp for this snapshot
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    video = relationship("TikTokVideo", back_populates="metrics_history")

class TikTokProduct(Base):
    __tablename__ = "tiktok_products"
    
    id = Column(String, primary_key=True)
    shop_id = Column(String, ForeignKey("tiktok_shops.shop_id"))
    product_id = Column(String, unique=True, index=True)
    product_name = Column(String)
    product_status = Column(Integer)
    category_id = Column(String)
    brand_id = Column(String)
    skus = Column(JSON)
    images = Column(JSON)
    create_time = Column(Integer)
    update_time = Column(Integer)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    shop = relationship("TikTokShop", back_populates="products")

class TikTokOrder(Base):
    __tablename__ = "tiktok_orders"
    
    id = Column(String, primary_key=True)
    shop_id = Column(String, ForeignKey("tiktok_shops.shop_id"))
    order_id = Column(String, unique=True, index=True)
    order_status = Column(Integer)
    payment_status = Column(String)
    fulfillment_type = Column(Integer)
    
    # Order data
    buyer_info = Column(JSON)
    recipient_address = Column(JSON)
    line_items = Column(JSON)
    payment_info = Column(JSON)
    shipping_info = Column(JSON)
    
    # Financial data
    total_amount = Column(Numeric(10, 2))
    currency = Column(String, default="USD")
    
    # Attribution data
    creator_id = Column(String, index=True)  # Which creator gets credit
    attributed_video_id = Column(String, ForeignKey("tiktok_videos.video_id"))
    attribution_method = Column(String)  # last_click, first_click, linear, etc.
    attribution_confidence = Column(Numeric(3, 2), default=1.00)  # 0.0 to 1.0
    
    # Timestamps
    create_time = Column(Integer)
    update_time = Column(Integer)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    shop = relationship("TikTokShop", back_populates="orders")
    attributed_video = relationship("TikTokVideo", back_populates="attributed_orders")

class CampaignVideoDeliverable(Base):
    __tablename__ = "campaign_video_deliverables"
    
    id = Column(String, primary_key=True)
    campaign_id = Column(String, index=True)
    deliverable_id = Column(String, index=True)
    creator_id = Column(String, index=True)
    video_id = Column(String, ForeignKey("tiktok_videos.video_id"))
    
    # Deliverable tracking
    submitted_at = Column(DateTime(timezone=True))
    approved_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    status = Column(String, default="pending")  # pending, approved, rejected
    
    # Review information
    reviewer_notes = Column(Text)
    reviewer_id = Column(String)
    
    # Performance tracking
    target_views = Column(Integer)
    target_engagement_rate = Column(Numeric(5, 2))
    meets_requirements = Column(Boolean)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Add the missing SyncOperation class
class SyncOperation(Base):
    __tablename__ = "sync_operations"
    
    id = Column(String, primary_key=True)
    shop_id = Column(String, ForeignKey("tiktok_shops.shop_id"))
    entity_type = Column(String)  # 'product', 'order', 'video'
    sync_mode = Column(String)  # 'full', 'incremental', 'changes_only'
    status = Column(String)  # 'in_progress', 'completed', 'failed'
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    estimated_completion = Column(DateTime(timezone=True))
    
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    errors = Column(JSON)
    sync_metadata = Column(JSON)  # Note: using sync_metadata instead of metadata
    
    # Relationships
    shop = relationship("TikTokShop")

# Add the missing WebhookEvent class
class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(String, primary_key=True)
    webhook_id = Column(String, unique=True, index=True)
    shop_id = Column(String, ForeignKey("tiktok_shops.shop_id"))
    event_type = Column(String, index=True)
    
    payload = Column(JSON)
    headers = Column(JSON)
    
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    status = Column(String, default="pending")  # 'pending', 'processed', 'failed', 'retrying'
    retry_count = Column(Integer, default=0)
    error_message = Column(String)
    
    # Relationships
    shop = relationship("TikTokShop")

# Add AuthCodeUsage class if it's missing
class AuthCodeUsage(Base):
    __tablename__ = "auth_code_usage"
    
    id = Column(String, primary_key=True)
    auth_code = Column(String, unique=True, index=True)
    used_at = Column(DateTime(timezone=True), server_default=func.now())