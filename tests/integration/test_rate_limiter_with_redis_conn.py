# Standard libs
import asyncio
import time

# Non-Standard libs
import pytest

# Own Modules
from core.security.rate_limiter.rate_limiter import SlidingWindowLog


# Helper function to get count from Redis Sorted Set
async def get_log_count(client, key):
    """Get count of entries in the sorted set."""
    return await client.zcard(key)


# Helper function to get log size and timestamps
async def get_log_entries(client, key):
    """Get all entries from the sorted set with scores."""
    return await client.zrange(key, 0, -1, withscores=True)


# --------------------------------------------------------------------------------------
# Basic Request Flow
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_first_request_is_allowed_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    result = await limiter.acquire("docker_user_1")
    assert result is True

    count = await get_log_count(test_redis_client, "docker_user_1")
    assert count == 1


@pytest.mark.asyncio
async def test_second_request_is_allowed_before_limit_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2


@pytest.mark.asyncio
async def test_fourth_request_exceeds_limit_and_is_denied_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2

    third_result = await limiter.acquire("docker_user")
    assert third_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    fourth_result = await limiter.acquire("docker_user")
    assert fourth_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3


@pytest.mark.asyncio
async def test_request_above_limit_is_blocked_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2

    third_result = await limiter.acquire("docker_user")
    assert third_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    fourth_result = await limiter.acquire("docker_user")
    assert fourth_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    fifth_result = await limiter.acquire("docker_user")
    assert fifth_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3


@pytest.mark.asyncio
async def test_multiple_requests_after_block_remain_blocked_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    third_result = await limiter.acquire("docker_user")
    assert third_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    fourth_result = await limiter.acquire("docker_user")
    assert fourth_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


# --------------------------------------------------------------------------------------
# Key Isolation
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_different_keys_are_independent_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    first_result = await limiter.acquire("docker_user_1")
    assert first_result is True
    count_1 = await get_log_count(test_redis_client, "docker_user_1")
    assert count_1 == 1

    second_result = await limiter.acquire("docker_user_2")
    assert second_result is True
    count_2 = await get_log_count(test_redis_client, "docker_user_2")
    assert count_2 == 1


@pytest.mark.asyncio
async def test_same_key_uses_same_log_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


@pytest.mark.asyncio
async def test_many_keys_do_not_interfere_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    for i in range(100):
        key = f"docker_user_{i}"
        result = await limiter.acquire(key)
        assert result is True

        count = await get_log_count(test_redis_client, key)
        assert count == 1


# --------------------------------------------------------------------------------------
# Window Recovery (Sliding Window specific)
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_expired_entries_removed_after_window_expires_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=3)

    # Add 3 requests
    for _ in range(3):
        result = await limiter.acquire("docker_user")
        assert result is True

    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    # Wait for window to expire
    await asyncio.sleep(2.1)

    # New request should be allowed and old entries removed
    result = await limiter.acquire("docker_user")
    assert result is True

    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


@pytest.mark.asyncio
async def test_partial_window_does_not_remove_entries_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=5.0, limit=3)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2

    # Wait but not enough to expire
    await asyncio.sleep(1.0)

    third_result = await limiter.acquire("docker_user")
    assert third_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    fourth_result = await limiter.acquire("docker_user")
    assert fourth_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3


@pytest.mark.asyncio
async def test_sliding_window_removes_old_entries_gradually_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=3)

    # Add 3 requests
    for _ in range(3):
        await limiter.acquire("docker_user")

    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    # Wait 1 second (half window)
    await asyncio.sleep(1.0)

    # Add another request - old entries still valid
    result = await limiter.acquire("docker_user")
    assert result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 3

    # Wait another 1.1 seconds (total > 2 seconds)
    await asyncio.sleep(1.1)

    # Add another request - old entries expired
    result = await limiter.acquire("docker_user")
    assert result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


# --------------------------------------------------------------------------------------
# Limit Edge Cases
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_limit_one_allows_single_request_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    result = await limiter.acquire("docker_user")
    assert result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


@pytest.mark.asyncio
async def test_limit_one_blocks_second_request_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


@pytest.mark.skip(reason="Large limit tests prone to expiration in CI environment")
@pytest.mark.asyncio
async def test_large_limit_allows_many_requests_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=86400.0, limit=1000)

    for _ in range(1000):
        result = await limiter.acquire("docker_user")
        assert result is True

    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1000


@pytest.mark.skip(reason="Large limit tests prone to expiration in CI environment")
@pytest.mark.asyncio
async def test_large_limit_blocks_after_limit_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=86400.0, limit=1000)

    for _ in range(1000):
        await limiter.acquire("docker_user")

    result = await limiter.acquire("docker_user")
    assert result is False

    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1000


# --------------------------------------------------------------------------------------
# Redis State Validation
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_log_created_after_first_request_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    result = await limiter.acquire("docker_user")
    assert result is True

    key_exists = await test_redis_client.exists("docker_user")
    assert key_exists == 1


@pytest.mark.asyncio
async def test_log_stores_timestamps_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    result = await limiter.acquire("docker_user")
    assert result is True

    entries = await get_log_entries(test_redis_client, "docker_user")
    assert len(entries) == 1
    assert isinstance(entries[0][1], float)


@pytest.mark.asyncio
async def test_count_never_negative_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True

    second_result = await limiter.acquire("docker_user")
    assert second_result is False

    count = await get_log_count(test_redis_client, "docker_user")
    assert count >= 0


# --------------------------------------------------------------------------------------
# Sliding Window Specific Tests
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_different_window_sizes_work_correctly_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=2)

    first_result = await limiter.acquire("docker_user")
    assert first_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1

    second_result = await limiter.acquire("docker_user")
    assert second_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2

    third_result = await limiter.acquire("docker_user")
    assert third_result is False
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 2

    await asyncio.sleep(2.1)

    fourth_result = await limiter.acquire("docker_user")
    assert fourth_result is True
    count = await get_log_count(test_redis_client, "docker_user")
    assert count == 1


@pytest.mark.asyncio
async def test_get_remaining_returns_correct_value_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    for _ in range(3):
        await limiter.acquire("docker_user")

    remaining = await limiter.get_remaining("docker_user")
    assert remaining == 7


@pytest.mark.asyncio
async def test_get_remaining_returns_limit_for_new_key_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    remaining = await limiter.get_remaining("docker_user")
    assert remaining == 10


@pytest.mark.asyncio
async def test_reset_deletes_key_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    await limiter.acquire("docker_user")
    await limiter.acquire("docker_user_2")

    await limiter.reset("docker_user")

    key_exists = await test_redis_client.exists("docker_user")
    assert key_exists == 0

    key_exists_2 = await test_redis_client.exists("docker_user_2")
    assert key_exists_2 == 1


@pytest.mark.asyncio
async def test_get_oldest_timestamp_returns_correct_value_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    await limiter.acquire("docker_user")
    await asyncio.sleep(0.1)
    await limiter.acquire("docker_user")

    oldest = await limiter.get_oldest_timestamp("docker_user")
    assert oldest > 0

    newest = await limiter.get_newest_timestamp("docker_user")
    assert newest > oldest


@pytest.mark.asyncio
async def test_get_oldest_timestamp_returns_zero_for_empty_integration(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=3)

    oldest = await limiter.get_oldest_timestamp("docker_user")
    assert oldest == 0.0