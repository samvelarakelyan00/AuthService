import asyncio
import pytest
from httpx import AsyncClient

from core.security.rate_limiter.rate_limiter import SlidingWindowLog
from core.security.rate_limiter.rate_limit_service import RateLimitService

URL_COMMON_PART = "/api/v1/auth"


# --------------------------------------------------------------------------------------
# Reverse Proxy Spoofing & Header Interception Checks
# --------------------------------------------------------------------------------------
@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_x_forwarded_for_spoofing_isolation(async_http_client: AsyncClient, test_redis_client,
                                                  monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "spoof_check@test.com"
    payload = {"email": email, "password": "password"}

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json=payload,
        headers={"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    )

    stored_user_ip = await test_redis_client.keys("rate:login:ip:203.0.113.195")
    stored_proxy_ip = await test_redis_client.keys("rate:login:ip:70.41.3.18")

    assert response.status_code in [200, 429]
    assert len(stored_user_ip) >= 1
    assert len(stored_proxy_ip) == 0


@pytest.mark.xfail(reason="Event loop issue with API requests - known issue")
@pytest.mark.asyncio
async def test_cloudflare_connecting_ip_precedence(async_http_client: AsyncClient, test_redis_client,
                                                   monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "cf_check@test.com"
    payload = {"email": email, "password": "password"}

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json=payload,
        headers={"CF-Connecting-IP": "198.51.100.42"}
    )

    stored_cf_ip = await test_redis_client.keys("rate:login:ip:198.51.100.42")
    assert len(stored_cf_ip) >= 1
    assert response.status_code in [200, 429]


# --------------------------------------------------------------------------------------
# Injection Attack Mitigation
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_key_injection_attack_safety(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    malicious_key = "user\r\nSET overflowed 1\r\n"

    result = await limiter.acquire(malicious_key)
    assert result is True

    arbitrary_key_exists = await test_redis_client.exists("overflowed")
    assert arbitrary_key_exists == 0


# --------------------------------------------------------------------------------------
# Distributed High-Velocity Exploitation (DDoS Sim)
# --------------------------------------------------------------------------------------
@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_distributed_attack_on_single_account(async_http_client: AsyncClient, test_redis_client,
                                                    monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    target_email = "victim@test.com"
    payload = {"email": target_email, "password": "password"}

    status_codes = []
    for i in range(10):
        response = await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json=payload,
            headers={"X-Forwarded-For": f"192.168.1.{i}"}
        )
        status_codes.append(response.status_code)
        await asyncio.sleep(0.01)

    assert status_codes.count(200) == 3
    assert status_codes.count(429) == 7


# --------------------------------------------------------------------------------------
# Multi-Namespace Scope Isolation
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_endpoint_namespace_and_key_isolation(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=1)

    login_key = RateLimitService.build_email_key("login", "attacker@test.com")
    signup_key = RateLimitService.build_email_key("signup", "attacker@test.com")

    login_res1 = await limiter.acquire(login_key)
    login_res2 = await limiter.acquire(login_key)
    signup_res1 = await limiter.acquire(signup_key)

    assert login_res1 is True
    assert login_res2 is False
    assert signup_res1 is True


# --------------------------------------------------------------------------------------
# Sliding Window Specific Security Tests
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sliding_window_expiration_security(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=2)

    result1 = await limiter.acquire("test_user")
    assert result1 is True
    result2 = await limiter.acquire("test_user")
    assert result2 is True

    result3 = await limiter.acquire("test_user")
    assert result3 is False

    await asyncio.sleep(2.1)

    result4 = await limiter.acquire("test_user")
    assert result4 is True


@pytest.mark.asyncio
async def test_sliding_window_count_accuracy(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=10)

    for _ in range(5):
        result = await limiter.acquire("test_user")
        assert result is True

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 5

    count = await limiter.get_current_count("test_user")
    assert count == 5


@pytest.mark.xfail(reason="Event loop issue with multiple requests")
@pytest.mark.asyncio
async def test_sliding_window_rate_limit_prevention(async_http_client: AsyncClient, test_redis_client,
                                                     monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "rate_limit_test@test.com"
    payload = {"email": email, "password": "password"}

    for _ in range(3):
        response = await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json=payload
        )
        assert response.status_code in [200, 429]

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json=payload
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_sliding_window_different_endpoints_isolation(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    login_limiter = SlidingWindowLog(window_size=60.0, limit=2)
    signup_limiter = SlidingWindowLog(window_size=60.0, limit=3)

    login_key = RateLimitService.build_email_key("login", "test@example.com")
    signup_key = RateLimitService.build_email_key("signup", "test@example.com")

    login_res1 = await login_limiter.acquire(login_key)
    assert login_res1 is True
    login_res2 = await login_limiter.acquire(login_key)
    assert login_res2 is True
    login_res3 = await login_limiter.acquire(login_key)
    assert login_res3 is False

    signup_res1 = await signup_limiter.acquire(signup_key)
    assert signup_res1 is True
    signup_res2 = await signup_limiter.acquire(signup_key)
    assert signup_res2 is True
    signup_res3 = await signup_limiter.acquire(signup_key)
    assert signup_res3 is True


@pytest.mark.asyncio
async def test_sliding_window_get_remaining_security(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=5)

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 5

    for _ in range(3):
        await limiter.acquire("test_user")

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 2

    for _ in range(3):
        await limiter.acquire("test_user")

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 0


@pytest.mark.asyncio
async def test_sliding_window_reset_security(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=60.0, limit=5)

    for _ in range(5):
        await limiter.acquire("test_user")

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 0

    await limiter.reset("test_user")

    remaining = await limiter.get_remaining("test_user")
    assert remaining == 5


@pytest.mark.asyncio
async def test_sliding_window_old_entries_removal(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=3)

    for _ in range(3):
        result = await limiter.acquire("test_user")
        assert result is True

    count = await limiter.get_current_count("test_user")
    assert count == 3

    await asyncio.sleep(2.1)

    result = await limiter.acquire("test_user")
    assert result is True

    count = await limiter.get_current_count("test_user")
    assert count == 1


@pytest.mark.asyncio
async def test_sliding_window_partial_expiration_security(test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    limiter = SlidingWindowLog(window_size=2.0, limit=3)

    for _ in range(3):
        await limiter.acquire("test_user")

    await asyncio.sleep(1.0)

    result = await limiter.acquire("test_user")
    assert result is False

    await asyncio.sleep(1.1)

    result = await limiter.acquire("test_user")
    assert result is True