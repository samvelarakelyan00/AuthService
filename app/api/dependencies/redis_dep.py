# Standard libs
from typing import AsyncGenerator

# Non-Standard libs
from fastapi import Request
import redis.asyncio as aioredis


async def get_redis(request: Request) -> AsyncGenerator[aioredis.Redis, None]:
    yield request.app.state.redis_client
