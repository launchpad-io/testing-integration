from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class AttributionMethod(enum.Enum):
    DIRECT_LINK = "direct_link"
    PROMO_CODE = "promo_code"
    COOKIE_BASED = "cookie_based"
    MANUAL = "manual"

class VideoStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    PENDING = "pending"

class DeliverableStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

class TikTokVideo(Base):
    __tablename__ = "tiktok_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tiktok_video_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Video metadata
    title = Column(String(500))
    description = Column(Text)
    video_url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    
    # Video metrics
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    
    # Attribution data
    promo_codes = Column(JSON)  # Store associated promo codes
    tracking_links = Column(JSON)  # Store tracking links used
    
    # Status and timestamps
    status = Column(Enum(VideoStatus), default=VideoStatus.ACTIVE)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    metrics = relationship("TikTokVideoMetrics", back_populates="video", cascade="all, delete-orphan")
    deliverables = relationship("CampaignVideoDeliverable", back_populates="video")
    attributed_orders = relationship("TikTokOrder", back_populates="attributed_video")

class TikTokVideoMetrics(Base):
    __tablename__ = "tiktok_video_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("tiktok_videos.id", ondelete="CASCADE"), nullable=False)
    
    # Metrics snapshot
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    
    # Calculated metrics
    engagement_rate = Column(Float, default=0.0)
    engagement_count = Column(Integer, default=0)
    
    # Attribution metrics
    attributed_gmv = Column(Float, default=0.0)
    attributed_orders = Column(Integer, default=0)
    
    # Timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    video = relationship("TikTokVideo", back_populates="metrics")

class CampaignVideoDeliverable(Base):
    __tablename__ = "campaign_video_deliverables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("tiktok_videos.id", ondelete="CASCADE"), nullable=False)
    creator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Deliverable details
    deliverable_type = Column(String(100))  # e.g., "post", "story", "reel"
    requirements_met = Column(JSON)  # Track which requirements are satisfied
    
    # Status and approval
    status = Column(Enum(DeliverableStatus), default=DeliverableStatus.PENDING)
    submitted_at = Column(DateTime)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    # Performance tracking
    performance_score = Column(Float)  # 0-100 score based on metrics
    bonus_eligible = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    video = relationship("TikTokVideo", back_populates="deliverables")

class TikTokOrder(Base):
    __tablename__ = "tiktok_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tiktok_order_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Enhanced order details
    total_amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    order_status = Column(String(50))
    
    # Attribution data
    creator_id = Column(UUID(as_uuid=True), index=True)
    attributed_video_id = Column(UUID(as_uuid=True), ForeignKey("tiktok_videos.id"), index=True)
    attribution_method = Column(Enum(AttributionMethod))
    attribution_confidence = Column(Float, default=0.0)  # 0.0 to 1.0
    
    # Promo code tracking
    promo_code_used = Column(String(50))
    discount_amount = Column(Float, default=0.0)
    
    # Customer information
    customer_id = Column(String(255))
    customer_email = Column(String(255))
    
    # Order timestamps
    order_date = Column(DateTime)
    fulfilled_date = Column(DateTime)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attributed_video = relationship("TikTokVideo", back_populates="attributed_orders")

class TikTokCreatorAuth(Base):
    __tablename__ = "tiktok_creator_auth"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    
    # OAuth credentials
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # TikTok user info
    tiktok_user_id = Column(String(255), unique=True, index=True)
    tiktok_username = Column(String(255))
    display_name = Column(String(255))
    
    # Permissions
    scopes = Column(JSON)  # Store granted scopes
    
    # Status
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 

class TikTokAccount(Base):
    __tablename__ = "tiktok_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    
    # OAuth credentials
    access_token = Column(Text)
    refresh_token = Column(Text)
    access_token_expire_in = Column(Integer)  # Expiry in seconds
    refresh_token_expire_in = Column(Integer)  # Expiry in seconds
    
    # TikTok user info
    tiktok_user_id = Column(String(255), unique=True, index=True)
    username = Column(String(255))
    display_name = Column(String(255))
    avatar_url = Column(String(500))
    
    # Account metrics
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    
    # Permissions and status
    scopes = Column(JSON)  # Store granted scopes
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    connected_at = Column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 