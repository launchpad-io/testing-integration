# app/models/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# -------------------- Async Database --------------------
# Create async engine (PostgreSQL with asyncpg driver recommended)
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,  # Ensure this setting exists in .env / config
    echo=settings.DEBUG,
)

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# -------------------- Sync Database (legacy compatibility) --------------------
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base model for both sync and async sessions
Base = declarative_base()

# -------------------- Dependency Helpers --------------------
# Async dependency for FastAPI routes/services
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Sync dependency kept to avoid breaking older code paths
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
