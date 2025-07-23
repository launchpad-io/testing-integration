# app/core/config.py - Update your existing config
from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "TikTok Shop Integration Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # TikTok Shop API settings
    TIKTOK_APP_KEY: str = os.getenv("TIKTOK_APP_KEY", "")
    TIKTOK_APP_SECRET: str = os.getenv("TIKTOK_APP_SECRET", "")
    TIKTOK_API_BASE_URL: str = "https://open-api.tiktokglobalshop.com"
    TIKTOK_AUTH_URL: str = "https://auth.tiktok-shops.com/oauth/authorize"
    TIKTOK_TOKEN_URL: str = "https://auth.tiktok-shops.com/api/v2/token"
    
    # TikTok Account Integration settings
    TIKTOK_CLIENT_ID: str = os.getenv("TIKTOK_CLIENT_ID", "")
    TIKTOK_CLIENT_SECRET: str = os.getenv("TIKTOK_CLIENT_SECRET", "")
    TIKTOK_REDIRECT_URI: str = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:3000/creator-dashboard/settings")
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:admin@localhost:5432/crm_campaigns_db")
    ASYNC_DATABASE_URL: str = os.getenv("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:admin@localhost:5432/crm_campaigns_db")
    
    # Redis settings (for caching tokens)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
    
    # JWT settings for internal auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8005"]
    
    # Webhook settings
    WEBHOOK_SECRET: Optional[str] = os.getenv("WEBHOOK_SECRET", None)
    
    # Security
    ALLOWED_HOSTS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# app/core/rate_limiter.py - Simplified version
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a simple limiter that doesn't require Redis
limiter = Limiter(key_func=get_remote_address)

