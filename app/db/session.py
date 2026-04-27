# Standard libs
# ...

# Non-Standard libs
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Own Modules
from core.config import settings


async_engine = create_async_engine(
    settings.db.DATABASE_URL,
    pool_size=settings.db.POOL_SIZE,
    max_overflow=settings.db.MAX_OVERFLOW,
    pool_timeout=settings.db.POOL_TIMEOUT,
    pool_recycle=settings.db.POOL_RECYCLE,
    pool_pre_ping=settings.db.POOL_PRE_PING
)

async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)
