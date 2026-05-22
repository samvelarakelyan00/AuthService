from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

# Import the pre-instantiated database manager from your session module
from db.session import db_manager
from db.redis_connection import redis_manager

from api.v1 import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing application infrastructure...")

    engine = db_manager.engine
    session_factory = db_manager.session_factory
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # 1. Verify Postgres Connection
    try:
        async with db_manager.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        print("Database connection verified successfully!")
    except Exception as error:
        print(f"Database connection verification failed: {error}")
        raise error

    app.state.redis_client = redis_manager.client

    # 2. Verify Redis Connection
    try:
        await redis_manager.client.ping()
        print("Redis connection verified successfully!")
    except Exception as error:
        print(f"Redis connection verification failed: {error}")
        raise error

    yield  # Application is running

    print("Initiating graceful connection teardown...")

    # Safely close all active connections held inside the SQLAlchemy engine pool
    await db_manager.engine.dispose()

    # Safely close the Redis client and disconnect its underlying connection pool
    await redis_manager.client.close()
    await redis_manager.pool.disconnect()

    print("All infrastructure resources safely released.")


# Initialize the FastAPI core instance with meta configurations and lifespan hook
app = FastAPI(
    title="Auth Service 2",
    description="Second Auth Service for getting ready, testing",
    version="0.0.1",
    lifespan=lifespan
)


app.include_router(v1_router, prefix="/api")


@app.get("/")
def root():
    """Simple health check endpoint."""
    return {"msg": "Server is running..."}


if __name__ == "__main__":
    # Using import string "main:app" allows the reload=True option to work perfectly
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
