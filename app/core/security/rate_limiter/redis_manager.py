# Non-Standard libs
import redis.asyncio as aioredis

# Own Modules
from core.settings import settings


class RedisConnectionManager:
    """
    Manages the lifecycle of the asynchronous Redis connection pool and client.

    Acts as a centralized container for caching and key-value store operations,
    ensuring unified pool configurations and proper client initialization.
    """
    def __init__(self) -> None:
        # Initialize the connection pool using global configurations
        self.pool = aioredis.ConnectionPool(
            host=settings.redis.HOST,
            port=settings.redis.PORT,
            db=settings.redis.DB,
            max_connections=settings.redis.MAX_CONNECTIONS,
            decode_responses=True  # Automatically decodes responses to UTF-8 strings
        )

        # Initialize the asynchronous Redis client using the configured pool
        self.client: aioredis.Redis = aioredis.Redis(connection_pool=self.pool)

    async def verify_redis_connection(self) -> None:
        await self.client.ping()


# Instantiate a single, global instance of the manager to be used across the application
redis_manager = RedisConnectionManager()