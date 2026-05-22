# Standard libs
# ...

# Non-Standard libs
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

# Own Modules
from core.settings import settings


class DatabaseSessionManager:
    """
    Manages the lifecycle of the SQLAlchemy asynchronous engine and session factory.

    Acts as a centralized container for database operations, ensuring unified
    pool configurations and proper engine initialization.
    """
    def __init__(self) -> None:
        # Initialize the asynchronous engine with optimized pool settings
        self.engine: AsyncEngine = create_async_engine(
            url=str(settings.DATABASE_URL),
            pool_size=settings.POOL_SIZE,
            max_overflow=settings.MAX_OVERFLOW,
            pool_timeout=settings.POOL_TIMEOUT,
            pool_recycle=settings.POOL_RECYCLE,
            pool_pre_ping=settings.POOL_PRE_PING,
            future=True,          # Enforces SQLAlchemy 2.0 API compliance
            echo=settings.DEBUG,  # SQL logging enabled only for local debugging
        )

        # Initialize the thread-safe, reusable async session factory
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Prevents implicit async lazy-loading exceptions
            autocommit=False,        # Requires explicit session.commit() calls
            autoflush=False,         # Prevents premature flushes before explicit commits
        )


# Instantiate a single, global instance of the manager to be used across the application
db_manager = DatabaseSessionManager()
