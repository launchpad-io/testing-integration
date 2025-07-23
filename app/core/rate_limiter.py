# app/core/rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import redis
from app.core.config import settings

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour"],
    storage_uri=settings.REDIS_URL if settings.REDIS_URL else "memory://"
)

def add_rate_limiting(app: FastAPI):
    """Add rate limiting middleware to FastAPI app"""
    app.state.limiter = limiter
    app.add_exception_handler(429, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

async def rate_limit_handler(request: Request, exc):
    """Custom rate limit exceeded handler"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else 60
        }
    )

