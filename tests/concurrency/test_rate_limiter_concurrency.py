# Standard libs
import asyncio

# Non-Standard libs
import pytest

# Own Modules
from core.security.rate_limiter.rate_limiter import SlidingWindowLog


# Helper to get count from Redis Sorted Set
async def get_log_count(client, key):
    """Get count of entries in the sorted set."""
    return await client.zcard(key)


# Helper to get all entries from the sorted set
async def get_log_entries(client, key):
    """Get all entries from the sorted set with scores."""
    return await client.zrange(key, 0, -1, withscores=True)


# --------------------------------------------------------------------------------------
# Same Key Concurrency
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_same_key_limit_one_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    async def worker():
        return await limiter.acquire("docker_concurrency_user")

    results = await asyncio.gather(*[worker() for _ in range(100)])

    assert sum(r is True for r in results) == 1
    assert sum(r is False for r in results) == 99

    count = await get_log_count(test_redis_client, "docker_concurrency_user")
    assert count == 1


@pytest.mark.asyncio
async def test_same_key_limit_five_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=5)

    async def worker():
        return await limiter.acquire("docker_concurrency_user")

    results = await asyncio.gather(*[worker() for _ in range(100)])

    assert sum(r is True for r in results) == 5
    assert sum(r is False for r in results) == 95

    count = await get_log_count(test_redis_client, "docker_concurrency_user")
    assert count == 5


@pytest.mark.asyncio
async def test_same_key_limit_ten_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    async def worker():
        return await limiter.acquire("docker_concurrency_user")

    results = await asyncio.gather(*[worker() for _ in range(1000)])

    assert sum(r is True for r in results) == 10
    assert sum(r is False for r in results) == 990

    count = await get_log_count(test_redis_client, "docker_concurrency_user")
    assert count == 10


# --------------------------------------------------------------------------------------
# Different Keys
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_different_keys_all_allowed_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    async def worker(index: int):
        return await limiter.acquire(f"docker_user_{index}")

    results = await asyncio.gather(*[worker(i) for i in range(100)])

    assert sum(r is True for r in results) == 100

    for i in range(100):
        count = await get_log_count(test_redis_client, f"docker_user_{i}")
        assert count == 1


@pytest.mark.asyncio
async def test_many_unique_keys_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    async def worker(index: int):
        return await limiter.acquire(f"docker_user_{index}")

    results = await asyncio.gather(*[worker(i) for i in range(1000)])

    assert sum(r is True for r in results) == 1000


# --------------------------------------------------------------------------------------
# Redis State Consistency
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_log_count_never_exceeds_limit_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    async def worker():
        return await limiter.acquire("docker_concurrency_user")

    await asyncio.gather(*[worker() for _ in range(100)])

    count = await get_log_count(test_redis_client, "docker_concurrency_user")
    assert count <= 3
    assert count >= 0


@pytest.mark.asyncio
async def test_log_created_once_for_same_key_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=5)

    async def worker():
        return await limiter.acquire("docker_concurrency_user")

    await asyncio.gather(*[worker() for _ in range(100)])

    assert await test_redis_client.exists("docker_concurrency_user") == 1


@pytest.mark.asyncio
async def test_log_count_matches_unique_keys_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    async def worker(index: int):
        return await limiter.acquire(f"docker_user_{index}")

    await asyncio.gather(*[worker(i) for i in range(100)])

    keys = await test_redis_client.keys("docker_user_*")
    assert len(keys) == 100


# --------------------------------------------------------------------------------------
# Lock Verification - No Race Conditions
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_double_allow_when_limit_one_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    async def worker():
        return await limiter.acquire("race_key")

    results = await asyncio.gather(*[worker() for _ in range(500)])

    assert results.count(True) == 1
    assert results.count(False) == 499

    count = await get_log_count(test_redis_client, "race_key")
    assert count == 1


@pytest.mark.asyncio
async def test_no_double_allow_when_limit_two_concurrency(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=2)

    async def worker():
        return await limiter.acquire("race_key")

    results = await asyncio.gather(*[worker() for _ in range(500)])

    assert results.count(True) == 2
    assert results.count(False) == 498

    count = await get_log_count(test_redis_client, "race_key")
    assert count == 2


# --------------------------------------------------------------------------------------
# Sliding Window Specific Concurrency Tests
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_sliding_window_expiration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=5)

    async def worker():
        return await limiter.acquire("sliding_user")

    # Fill the window
    results1 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results1.count(True) == 5

    # Try more - should be blocked
    results2 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results2.count(True) == 0

    # Wait for entries to expire
    await asyncio.sleep(2.1)

    # New requests should be allowed as old entries expired
    results3 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results3.count(True) == 5

    count = await get_log_count(test_redis_client, "sliding_user")
    assert count == 5


@pytest.mark.asyncio
async def test_concurrent_different_window_sizes(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    # Use a very large window to prevent expiration during the test
    small_window = SlidingWindowLog(window_size=2.0, limit=2)
    large_window = SlidingWindowLog(window_size=3600.0, limit=5)  # 1 hour window

    async def small_worker():
        return await small_window.acquire("small_user")

    async def large_worker():
        return await large_window.acquire("large_user")

    # Run sequentially to avoid timing issues
    small_results = []
    for _ in range(10):
        small_results.append(await small_worker())

    large_results = []
    for _ in range(10):
        large_results.append(await large_worker())

    assert small_results.count(True) == 2
    assert small_results.count(False) == 8

    assert large_results.count(True) == 5
    assert large_results.count(False) == 5


@pytest.mark.asyncio
async def test_concurrent_get_remaining(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    # Use a very large window to prevent expiration during the test
    limiter = SlidingWindowLog(window_size=3600.0, limit=10)

    async def worker():
        return await limiter.acquire("remaining_user")

    # Consume 3 requests
    for _ in range(3):
        await worker()

    # Check remaining
    remaining = await limiter.get_remaining("remaining_user")
    assert remaining == 7

    # Consume 3 more
    for _ in range(3):
        await worker()

    # Check remaining after consuming 3 more
    remaining = await limiter.get_remaining("remaining_user")
    assert remaining == 4

    # Verify total log count is 6
    count = await get_log_count(test_redis_client, "remaining_user")
    assert count == 6


@pytest.mark.asyncio
async def test_concurrent_different_endpoints(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=2)

    from core.security.rate_limiter.rate_limit_service import RateLimitService

    login_key = RateLimitService.build_email_key("login", "test@example.com")
    signup_key = RateLimitService.build_email_key("signup", "test@example.com")

    async def login_worker():
        return await limiter.acquire(login_key)

    async def signup_worker():
        return await limiter.acquire(signup_key)

    login_tasks = [login_worker() for _ in range(5)]
    signup_tasks = [signup_worker() for _ in range(5)]

    all_results = await asyncio.gather(*(login_tasks + signup_tasks))

    login_results = all_results[:5]
    signup_results = all_results[5:]

    assert login_results.count(True) == 2
    assert login_results.count(False) == 3
    assert signup_results.count(True) == 2
    assert signup_results.count(False) == 3


@pytest.mark.asyncio
async def test_concurrent_partial_expiration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=5)

    async def worker():
        return await limiter.acquire("partial_user")

    # Add 5 requests
    results1 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results1.count(True) == 5

    # Wait 1 second (half window)
    await asyncio.sleep(1.0)

    # Still at limit (no entries expired yet)
    results2 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results2.count(True) == 0

    # Wait 1.1 more seconds (total > 2 seconds)
    await asyncio.sleep(1.1)

    # Old entries expired, new requests allowed
    results3 = await asyncio.gather(*[worker() for _ in range(5)])
    assert results3.count(True) == 5


@pytest.mark.asyncio
async def test_concurrent_timestamp_ordering(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    async def worker(index: int):
        return await limiter.acquire("timestamp_user")

    # Make concurrent requests
    results = await asyncio.gather(*[worker(i) for i in range(10)])

    # All should be allowed
    assert results.count(True) == 10

    # Check log entries have timestamps
    entries = await get_log_entries(test_redis_client, "timestamp_user")
    assert len(entries) == 10

    # All timestamps should be valid floats
    for member, score in entries:
        assert isinstance(score, float)
        assert score > 0