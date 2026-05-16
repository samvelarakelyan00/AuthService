# Standard libs
# ...

# Non-Standard libs
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)

# Own Modules
from core.config import settings


def create_postgres_engine():
    """Создает экземпляр асинхронного движка SQLAlchemy."""
    return create_async_engine(
        settings.db.DATABASE_URL,
        pool_size=settings.db.POOL_SIZE,
        max_overflow=settings.db.MAX_OVERFLOW,
        pool_timeout=settings.db.POOL_TIMEOUT,
        pool_recycle=settings.db.POOL_RECYCLE,
        pool_pre_ping=settings.db.POOL_PRE_PING
    )

def create_postgres_sessionmaker(engine):
    """Создает фабрику сессий на основе переданного движка."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )