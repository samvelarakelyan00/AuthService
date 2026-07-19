# Non-Standard libs
from fastapi import Request

# Own Modules
from core.security.rate_limiter.rate_limit_guard import RateLimitGuard
from core.security.rate_limiter.rate_limit_profiles import (
    SIGNUP_IP_LIMITER, SIGNUP_EMAIL_LIMITER,
    LOGIN_IP_LIMITER, LOGIN_EMAIL_LIMITER,
    REFRESH_TOKEN_IP_LIMITER, REFRESH_TOKEN_EMAIL_LIMITER
)


async def get_signup_rate_limiter(request: Request) -> None:
    guard = RateLimitGuard(
        endpoint_identifier="signup",
        ip_limiter=SIGNUP_IP_LIMITER,
        account_limiter=SIGNUP_EMAIL_LIMITER
    )

    await guard(request)


async def get_login_rate_limiter(request: Request) -> None:
    guard = RateLimitGuard(
        endpoint_identifier="login",
        ip_limiter=LOGIN_IP_LIMITER,
        account_limiter=LOGIN_EMAIL_LIMITER
    )

    await guard(request)


async def get_refresh_token_rate_limiter(request: Request) -> None:
    guard = RateLimitGuard(
        endpoint_identifier="refresh_token",
        ip_limiter=REFRESH_TOKEN_IP_LIMITER,
        account_limiter=REFRESH_TOKEN_EMAIL_LIMITER
    )

    await guard(request)