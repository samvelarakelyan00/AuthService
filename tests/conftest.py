# Standard libs
import sys
from typing import Generator, AsyncGenerator
import asyncio
# Non-Standard libs
from httpx import AsyncClient, ASGITransport
import jwt
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from testcontainers.redis import RedisContainer
import warnings

# Force Pytest to find the warning class where it's looking for it
if not hasattr(jwt.exceptions, "InsecureKeyLengthWarning"):
    import jwt.warnings
    sys.modules["jwt.exceptions"].InsecureKeyLengthWarning = getattr(
        jwt.warnings, "InsecureKeyLengthWarning", UserWarning
    )


# Suppress event loop warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    """Create a single event loop for the entire test session."""
    loop = event_loop_policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    """Spins up an isolated Redis Docker container."""
    container = RedisContainer("redis:7-alpine")
    with container:
        yield container


@pytest_asyncio.fixture(scope="function")
async def test_redis_client(redis_container, monkeypatch, event_loop) -> AsyncGenerator[aioredis.Redis, None]:
    """Creates a Redis client with proper event loop management."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(redis_container.port)

    client = aioredis.Redis(
        host=host,
        port=int(port),
        decode_responses=True,
        max_connections=1000,
        socket_timeout=5,
        socket_connect_timeout=5,
    )

    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", client)

    await client.flushdb()
    yield client
    await client.flushdb()


@pytest_asyncio.fixture(scope="function")
async def async_http_client(test_redis_client, event_loop) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with proper event loop."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="function")
def asyncio_loop(event_loop):
    """Use the same event loop for all tests."""
    return event_loop