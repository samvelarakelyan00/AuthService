import redis.asyncio as aioredis
from core.config import settings # Предполагаем, что REDIS_URL находится тут

def init_redis_client() -> aioredis.Redis:
    """Инициализирует асинхронный клиент Redis с пулом соединений."""
    redis_pool = aioredis.ConnectionPool(
        host="redis",  # или settings.redis.HOST
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=50
    )

    return aioredis.Redis(connection_pool=redis_pool)
