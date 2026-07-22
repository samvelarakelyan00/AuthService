# # Standard libs
# import sys
# from typing import Generator, AsyncGenerator
# import asyncio
# # Non-Standard libs
# from httpx import AsyncClient, ASGITransport
# import jwt
# import pytest
# import pytest_asyncio
# import redis.asyncio as aioredis
# from testcontainers.redis import RedisContainer
# import warnings
#
# # Force Pytest to find the warning class where it's looking for it
# if not hasattr(jwt.exceptions, "InsecureKeyLengthWarning"):
#     import jwt.warnings
#     sys.modules["jwt.exceptions"].InsecureKeyLengthWarning = getattr(
#         jwt.warnings, "InsecureKeyLengthWarning", UserWarning
#     )
#
#
# # Suppress event loop warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)
#
#
# @pytest.fixture(scope="session")
# def event_loop_policy():
#     """Set the event loop policy for the test session."""
#     return asyncio.DefaultEventLoopPolicy()
#
#
# @pytest.fixture(scope="session")
# def event_loop(event_loop_policy):
#     """Create a single event loop for the entire test session."""
#     loop = event_loop_policy.new_event_loop()
#     asyncio.set_event_loop(loop)
#     yield loop
#     loop.close()
#
#
# @pytest.fixture(scope="session")
# def redis_container() -> Generator[RedisContainer, None, None]:
#     """Spins up an isolated Redis Docker container."""
#     container = RedisContainer("redis:7-alpine")
#     with container:
#         yield container
#
#
# @pytest_asyncio.fixture(scope="function")
# async def test_redis_client(redis_container, monkeypatch, event_loop) -> AsyncGenerator[aioredis.Redis, None]:
#     """Creates a Redis client with proper event loop management."""
#     host = redis_container.get_container_host_ip()
#     port = redis_container.get_exposed_port(redis_container.port)
#
#     client = aioredis.Redis(
#         host=host,
#         port=int(port),
#         decode_responses=True,
#         max_connections=1000,
#         socket_timeout=5,
#         socket_connect_timeout=5,
#     )
#
#     monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", client)
#
#     await client.flushdb()
#     yield client
#     await client.flushdb()
#
#
# @pytest_asyncio.fixture(scope="function")
# async def async_http_client(test_redis_client, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
#     from app.main import app
#     from db.session import db_manager
#     from core.security.rate_limiter.redis_manager import redis_manager
#
#     # Force the application state to contain the required objects
#     app.state.db_session_factory = db_manager.session_factory
#     app.state.redis_client = test_redis_client  # use the test Redis client
#
#     # Ensure the rate limiter's Redis manager is also patched (done by test_redis_client fixture)
#     # but we also need to patch the global redis_manager used in the service?
#     # The test_redis_client fixture already does monkeypatch.setattr for redis_manager.client,
#     # so that's covered.
#
#     # Now create the HTTP client with ASGI transport
#     async with AsyncClient(
#         transport=ASGITransport(app=app),
#         base_url="http://testserver"
#     ) as client:
#         yield client
#
#
# @pytest.fixture(scope="function")
# def asyncio_loop(event_loop):
#     """Use the same event loop for all tests."""
#     return event_loop





# Standard libs
import sys
import asyncio
from typing import Generator, AsyncGenerator

# Non-Standard libs
from httpx import AsyncClient, ASGITransport
import jwt
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer
import warnings

# Force Pytest to find the warning class
if not hasattr(jwt.exceptions, "InsecureKeyLengthWarning"):
    import jwt.warnings
    sys.modules["jwt.exceptions"].InsecureKeyLengthWarning = getattr(
        jwt.warnings, "InsecureKeyLengthWarning", UserWarning
    )

warnings.filterwarnings("ignore", category=DeprecationWarning)


# ---------- Event Loop ----------
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    loop = event_loop_policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ---------- Test Containers ----------
@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    container = RedisContainer("redis:7-alpine")
    with container:
        yield container


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    container = PostgresContainer("postgres:16-alpine")
    with container:
        yield container


# ---------- Test Redis Client ----------
@pytest_asyncio.fixture(scope="function")
async def test_redis_client(redis_container, monkeypatch, event_loop) -> AsyncGenerator[aioredis.Redis, None]:
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

    # Patch the global redis_manager used by the rate limiter
    from core.security.rate_limiter.redis_manager import redis_manager
    monkeypatch.setattr(redis_manager, "client", client)

    await client.flushdb()
    yield client
    await client.flushdb()


# ---------- Test DB Engine & Session ----------
@pytest_asyncio.fixture(scope="function")
async def test_db_engine(postgres_container, monkeypatch, event_loop):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from db.session import db_manager

    # Build connection string for asyncpg
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user = postgres_container.username
    password = postgres_container.password
    database = postgres_container.dbname

    sync_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create a new engine and session factory for the test
    engine = create_async_engine(async_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Patch the global db_manager to use our test engine
    monkeypatch.setattr(db_manager, "engine", engine)
    monkeypatch.setattr(db_manager, "session_factory", session_factory)

    # Also ensure the app's state will use these
    yield engine, session_factory

    # Cleanup
    await engine.dispose()


# ---------- HTTP Client with Lifespan ----------
@pytest_asyncio.fixture(scope="function")
async def async_http_client(
    test_redis_client,
    test_db_engine,
    monkeypatch,
    event_loop
) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from db.session import db_manager

    # Force the application state to use the test factories
    app.state.db_session_factory = db_manager.session_factory
    app.state.redis_client = test_redis_client

    # Also ensure that the rate limiter's redis_manager is already patched by test_redis_client

    # Create the HTTP client with ASGI transport
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture(scope="function")
def asyncio_loop(event_loop):
    return event_loop