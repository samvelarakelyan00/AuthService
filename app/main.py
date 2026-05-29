"""
Main Application Entry Point.

Configures the FastAPI core runtime instance, hooks into the infrastructure
lifespan manager, applies routes, and bootstraps industrial logging targets.
"""

# Standard libs
import logging
from contextlib import asynccontextmanager

# Non-Standard libs
import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

# Own Modules
from db.session import db_manager
from db.redis_connection import redis_manager
from core.logger import initialize_system_logging
# Routers
from api.v1 import v1_router


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
    logger = logging.getLogger("main")
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

    logger.info("All components are healthy. Microservice startup complete.")
    yield  # Application is running and accepting active network traffic

    logger.warning("Initiating graceful infrastructure teardown sequencing...")

    # Safely close all active connections held inside the SQLAlchemy engine pool
    await db_manager.engine.dispose()
    logger.info("SQLAlchemy database connection pools gracefully closed.")

    # Safely close the Redis client and disconnect its underlying connection pool
    await redis_manager.client.close()
    await redis_manager.pool.disconnect()
    logger.info("Redis non-blocking operational connections safely disconnected.")

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


if __name__ == "__main__":
    # Using import string "main:app" allows the reload=True option to work perfectly
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
