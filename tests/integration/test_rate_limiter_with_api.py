# Standard libs
from httpx import AsyncClient

# Non-Standard libs
import pytest


URL_COMMON_PART = "/api/v1/auth"


# --------------------------------------------------------------------------------------
# Root Endpoint
# --------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_root_returns_200(async_http_client: AsyncClient) -> None:
    response = await async_http_client.get("/")
    assert response.status_code == 200


# --------------------------------------------------------------------------------------
# Login Endpoint
# --------------------------------------------------------------------------------------
@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_login_first_request_allowed(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "first@test.com",
            "password": "password"
        }
    )

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
async def test_login_email_limit_blocks_fourth_request(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "blocked@test.com"

    for _ in range(3):
        await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json={
                "email": email,
                "password": "password"
            }
        )

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": email,
            "password": "password"
        }
    )

    assert response.status_code == 429


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_login_email_normalization(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "TestUser@gmail.com",
            "password": "password"
        }
    )

    await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "testuser@gmail.com",
            "password": "password"
        }
    )

    await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "TESTUSER@gmail.com",
            "password": "password"
        }
    )

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "testuser@gmail.com",
            "password": "password"
        }
    )

    assert response.status_code == 429


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_signup_first_request_allowed(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john",
            "email": "john@test.com",
            "plain_password": "password"
        }
    )

    assert response.status_code == 201


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_signup_email_limit_blocks_third_request(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "signup@test.com"

    response_1 = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john",
            "email": email,
            "plain_password": "password"
        }
    )

    response_2 = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john2",
            "email": email,
            "plain_password": "password"
        }
    )

    response_3 = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john3",
            "email": email,
            "plain_password": "password"
        }
    )

    assert response_1.status_code == 201
    assert response_2.status_code == 201
    assert response_3.status_code == 429


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_signup_different_emails_are_independent(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    response_1 = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "user1",
            "email": "user1@test.com",
            "plain_password": "password"
        }
    )

    response_2 = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "user2",
            "email": "user2@test.com",
            "plain_password": "password"
        }
    )

    assert response_1.status_code == 201
    assert response_2.status_code == 201


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_login_limiter_does_not_affect_signup(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "isolation@test.com"

    for _ in range(3):
        await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json={
                "email": email,
                "password": "password"
            }
        )

    login_response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": email,
            "password": "password"
        }
    )

    signup_response = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john",
            "email": email,
            "plain_password": "password"
        }
    )

    assert login_response.status_code == 429
    assert signup_response.status_code == 201


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_signup_limiter_does_not_affect_login(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "cross@test.com"

    await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john",
            "email": email,
            "plain_password": "password"
        }
    )

    await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john2",
            "email": email,
            "plain_password": "password"
        }
    )

    signup_response = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "john3",
            "email": email,
            "plain_password": "password"
        }
    )

    login_response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": email,
            "password": "password"
        }
    )

    assert signup_response.status_code == 429
    assert login_response.status_code == 200


# --------------------------------------------------------------------------------------
# Sliding Window Log Specific API Tests
# --------------------------------------------------------------------------------------
@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_login_ip_limit_blocks_after_limit(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    for i in range(3):
        response = await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json={
                "email": f"user{i}@test.com",
                "password": "password"
            }
        )
        assert response.status_code == 200

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": "blocked@test.com",
            "password": "password"
        }
    )
    assert response.status_code == 429


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_signup_ip_limit_blocks_after_limit(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    for i in range(5):
        response = await async_http_client.post(
            f"{URL_COMMON_PART}/signup",
            json={
                "username": f"user{i}",
                "email": f"user{i}@test.com",
                "plain_password": "password"
            }
        )
        assert response.status_code == 201

    response = await async_http_client.post(
        f"{URL_COMMON_PART}/signup",
        json={
            "username": "blocked",
            "email": "blocked@test.com",
            "plain_password": "password"
        }
    )
    assert response.status_code == 429


@pytest.mark.xfail(reason="Event loop issue with multiple requests...test postgres container users table does not exist")
@pytest.mark.asyncio
async def test_sliding_window_allows_after_old_entries_expire(async_http_client: AsyncClient, test_redis_client, monkeypatch) -> None:
    monkeypatch.setattr("core.security.rate_limiter.redis_manager.redis_manager.client", test_redis_client)

    email = "sliding@test.com"

    # Make 3 requests (limit is 3 per window)
    for _ in range(3):
        response = await async_http_client.post(
            f"{URL_COMMON_PART}/login",
            json={
                "email": email,
                "password": "password"
            }
        )
        assert response.status_code == 200

    # Fourth request should be blocked
    response = await async_http_client.post(
        f"{URL_COMMON_PART}/login",
        json={
            "email": email,
            "password": "password"
        }
    )
    assert response.status_code == 429

    # Wait for window to expire (using a small window would be better,
    # but we'll rely on the Redis connection tests for this)
    pass