# Standard libs
import asyncio
import logging
from contextlib import asynccontextmanager

# Non-Standard libs
from fastapi import FastAPI
from sqlalchemy import text

# Own Modules
from core.settings import settings
from core.logger import initialize_system_logging
from core.kafka.connection import kafka_manager
from db.session import db_manager
from db.redis_connection import redis_manager
from tasks.cleanup_unverified_users import cleanup_unverified_users
from api.v1 import v1_router


# Instantiate isolated service tracer bound to this module namespace
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the operational lifecycle of core external application dependencies.
    Bootstraps structured log outputs first, verifies stateful persistence
    networks on startup, and guarantees safe connection teardowns during shutdown frames.
    """

    # 1. Initialize global logging configuration dictionary
    initialize_system_logging()

    # 2. Instantiate the explicit main system logger now that configuration is safely active
    logger.info("Application logging subsystem successfully attached to ASGI lifecycle.")
    logger.info("Initializing application infrastructure targets...")

    engine = db_manager.engine
    session_factory = db_manager.session_factory
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # 3. Verify Postgres Connection
    try:
        async with db_manager.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database infrastructure connection pools verified successfully.")
    except Exception as error:
        logger.critical(
            "Database connection verification failed abruptly: %s",
            error,
            exc_info=True
        )
        raise error

    app.state.redis_client = redis_manager.client

    # 4. Verify Redis Connection
    try:
        await redis_manager.client.ping()
        logger.info("Redis cache cluster infrastructure verified successfully.")
    except Exception as error:
        logger.critical(
            "Redis connection verification failed abruptly: %s",
            error,
            exc_info=True
        )
        raise error

    # 5. Initialize Kafka
    try:
        await kafka_manager.initialize()
        logger.info("Kafka connection initialized successfully.")
    except Exception as error:
        logger.critical(
            "Kafka connection verification failed: %s",
            error,
            exc_info=True
        )
        raise error

    # 6. Start background cleanup task
    cleanup_interval_seconds = settings.CLEANUP_INTERVAL_DAYS * 24 * 60 * 60

    async def periodic_cleanup():
        while True:
            try:
                await asyncio.sleep(cleanup_interval_seconds)
                await cleanup_unverified_users()
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled.")
                break
            except Exception as error:
                logger.error(
                    "Error in cleanup task: %s",
                    str(error),
                    exc_info=True
                )

    app.state.cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info(
        "User cleanup task scheduled (runs every %d days).",
        settings.CLEANUP_INTERVAL_DAYS
    )

    logger.info("All components are healthy. Microservice startup complete.")
    yield  # Application is running and accepting active network traffic

    logger.warning("Initiating graceful infrastructure teardown sequencing...")

    # Cancel cleanup task on shutdown
    if hasattr(app.state, "cleanup_task"):
        app.state.cleanup_task.cancel()
        try:
            await app.state.cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("User cleanup task cancelled.")

    # Safely close all active connections held inside the SQLAlchemy engine pool
    await db_manager.engine.dispose()
    logger.info("SQLAlchemy database connection pools gracefully closed.")

    # Safely close the Redis client and disconnect its underlying connection pool
    await redis_manager.client.close()
    await redis_manager.pool.disconnect()
    logger.info("Redis non-blocking operational connections safely disconnected.")

    # Shutdown Kafka
    await kafka_manager.shutdown()
    logger.info("Kafka connections gracefully closed.")

    logger.info("All infrastructure resources safely released. System halt completed.")


# Initialize the FastAPI core instance with meta configurations and lifespan hook
app = FastAPI(
    title="Auth Service 2",
    description="Second Auth Service for getting ready, testing",
    version="0.0.1",
    lifespan=lifespan
)

# Attach API Routing Architecture
app.include_router(v1_router, prefix="/api")


@app.get("/")
def root():
    """Simple health check endpoint."""
    # We dynamically fetch the configured "main" logger instance to prevent pre-import leakage
    logging.getLogger("main").debug("Root path / verification probe hit.")
    return {"msg": "Server is running..."}


@app.get("/simulate-error", tags=["Infrastructure"])
def simulate_error():
    """Intentional division by zero to verify systemic error capture."""
    try:
        result = 1 / 0
        return {"result": result}
    except ZeroDivisionError:
        logging.getLogger("main").error("Critical failure event initiated on fault route.")