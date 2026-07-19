# Standard libs
from typing import Optional, Dict, Any
import json

# Non-Standard libs
from fastapi import (
    status,
    Request,
    HTTPException
)

# Own Modules
from core.security.rate_limiter.rate_limiter import SlidingWindowLog
from core.security.rate_limiter.rate_limit_service import RateLimitService


class RateLimitGuard:
    """
    FastAPI dependency guard for rate limiting.

    Intercepts incoming requests and applies rate limiting based on:
    1. Client IP address (always applied)
    2. Account/Email identifier (optional, applied if present in request body)

    Supports both IP-based and account-based rate limiting with configurable
    limiters and body size restrictions.
    """

    def __init__(
        self,
        endpoint_identifier: str,
        ip_limiter: SlidingWindowLog,
        account_limiter: Optional[SlidingWindowLog] = None,
        max_body_bytes: int = 1024 * 50,
        require_email: bool = False,
        email_field_name: str = "email",
        bypass_methods: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize the rate limit guard.

        :param endpoint_identifier: Unique identifier for the endpoint (e.g., 'login', 'signup')
        :param ip_limiter: Rate limiter instance for IP-based limiting
        :param account_limiter: Optional rate limiter for account/email-based limiting
        :param max_body_bytes: Maximum allowed request body size in bytes
        :param require_email: If True, requests without email will be rejected
        :param email_field_name: Field name for email in request body (default: 'email')
        :param bypass_methods: HTTP methods to bypass rate limiting (e.g., ['OPTIONS'])
        """
        self.endpoint_identifier = endpoint_identifier
        self.ip_limiter = ip_limiter
        self.account_limiter = account_limiter
        self.max_body_bytes = max_body_bytes
        self.require_email = require_email
        self.email_field_name = email_field_name
        self.bypass_methods = bypass_methods or []

    async def __call__(self, request: Request) -> None:
        """
        Execute the rate limit check.

        :param request: FastAPI Request object
        :raises HTTPException: If rate limit is exceeded or request is invalid
        """
        # Bypass rate limiting for certain methods (e.g., OPTIONS, HEAD)
        if request.method in self.bypass_methods:
            return

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Request body too large. Maximum allowed: {self.max_body_bytes} bytes"
            )

        # --- IP-based rate limiting (always applied) ---
        client_ip = RateLimitService.extract_client_ip(request)
        ip_key = RateLimitService.build_ip_key(self.endpoint_identifier, client_ip)

        if not await self.ip_limiter.acquire(ip_key):
            RateLimitService.raise_ip_limit_exceeded()

        # --- Account/Email-based rate limiting (optional) ---
        if not self.account_limiter:
            return

        try:
            body = await self._safe_parse_json(request)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in request body"
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse request body: {str(err)}"
            )

        email = body.get(self.email_field_name)

        if self.require_email and not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: '{self.email_field_name}'"
            )

        if not email:
            return

        email_key = RateLimitService.build_email_key(self.endpoint_identifier, email)

        if not await self.account_limiter.acquire(email_key):
            RateLimitService.raise_email_limit_exceeded()

    async def _safe_parse_json(self, request: Request) -> Dict[str, Any]:
        """
        Safely parse JSON from request body.

        :param request: FastAPI Request object
        :return: Parsed JSON dictionary
        :raises json.JSONDecodeError: If JSON is invalid
        """
        try:
            return await request.json()
        except json.JSONDecodeError:
            # Try to read body as bytes and decode manually
            body_bytes = await request.body()
            if body_bytes:
                return json.loads(body_bytes.decode('utf-8'))
            return {}

    async def get_remaining_capacity(self, request: Request) -> Dict[str, Any]:
        """
        Get remaining capacity for the current request context.
        Useful for returning rate limit headers.

        :param request: FastAPI Request object
        :return: Dictionary with remaining capacities
        """
        result = {}

        # IP limit remaining
        client_ip = RateLimitService.extract_client_ip(request)
        ip_key = RateLimitService.build_ip_key(self.endpoint_identifier, client_ip)
        result['ip_remaining'] = await self.ip_limiter.get_remaining(ip_key)

        # Account limit remaining (if applicable)
        if self.account_limiter:
            try:
                body = await self._safe_parse_json(request)
                email = body.get(self.email_field_name)
                if email:
                    email_key = RateLimitService.build_email_key(self.endpoint_identifier, email)
                    result['account_remaining'] = await self.account_limiter.get_remaining(email_key)
            except:
                pass

        return result

    async def reset_limits(self, ip: Optional[str] = None, email: Optional[str] = None) -> None:
        """
        Manually reset rate limits for a specific IP or email.
        Useful for administrative purposes.

        :param ip: IP address to reset limits for
        :param email: Email to reset limits for
        """
        if ip:
            ip_key = RateLimitService.build_ip_key(self.endpoint_identifier, ip)
            await self.ip_limiter.reset(ip_key)

        if email and self.account_limiter:
            email_key = RateLimitService.build_email_key(self.endpoint_identifier, email)
            await self.account_limiter.reset(email_key)