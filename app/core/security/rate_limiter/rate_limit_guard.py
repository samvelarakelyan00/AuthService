# Standard libs
from typing import Optional, Dict, Any
import json
import logging

# Non-Standard libs
from fastapi import (
    status,
    Request,
    HTTPException,
)

# Own Modules
from core.security.rate_limiter.rate_limiter import SlidingWindowLog
from core.security.rate_limiter.rate_limit_service import RateLimitService

# Module-level logger
logger = logging.getLogger(__name__)


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

        logger.debug(
            "RateLimitGuard initialised",
            extra={
                "endpoint": endpoint_identifier,
                "ip_limit": ip_limiter.limit,
                "ip_window": ip_limiter.window_size,
                "account_limiter_enabled": account_limiter is not None,
                "account_limit": account_limiter.limit if account_limiter else None,
                "account_window": account_limiter.window_size if account_limiter else None,
                "require_email": require_email,
                "max_body_bytes": max_body_bytes,
            },
        )

    async def __call__(self, request: Request) -> None:
        """
        Execute the rate limit check.

        :param request: FastAPI Request object
        :raises HTTPException: If rate limit is exceeded or request is invalid
        """
        # Bypass rate limiting for certain methods (e.g., OPTIONS, HEAD)
        if request.method in self.bypass_methods:
            logger.debug(
                "Rate limit bypassed for method",
                extra={"method": request.method, "endpoint": self.endpoint_identifier},
            )
            return

        client_ip = RateLimitService.extract_client_ip(request)

        # Log the incoming request at DEBUG level
        logger.debug(
            "Rate limit guard processing request",
            extra={
                "endpoint": self.endpoint_identifier,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        )

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_bytes:
            logger.warning(
                "Request body too large",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "client_ip": client_ip,
                    "content_length": int(content_length),
                    "max_body_bytes": self.max_body_bytes,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Request body too large. Maximum allowed: {self.max_body_bytes} bytes",
            )

        # --- IP-based rate limiting (always applied) ---
        ip_key = RateLimitService.build_ip_key(self.endpoint_identifier, client_ip)

        # Get remaining capacity before consuming (for logging)
        ip_remaining_before = await self.ip_limiter.get_remaining(ip_key)

        ip_allowed = await self.ip_limiter.acquire(ip_key)

        if not ip_allowed:
            # Denied – log at WARNING level with full context
            logger.warning(
                "Rate limit exceeded for IP",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "scope": "ip",
                    "identifier": client_ip,
                    "window_size": self.ip_limiter.window_size,
                    "limit": self.ip_limiter.limit,
                    "remaining_before": ip_remaining_before,
                    "allowed": False,
                },
            )
            RateLimitService.raise_ip_limit_exceeded()

        # Allowed – log at DEBUG level
        logger.debug(
            "Rate limit check passed for IP",
            extra={
                "endpoint": self.endpoint_identifier,
                "scope": "ip",
                "identifier": client_ip,
                "window_size": self.ip_limiter.window_size,
                "limit": self.ip_limiter.limit,
                "remaining_before": ip_remaining_before,
                "allowed": True,
            },
        )

        # --- Account/Email-based rate limiting (optional) ---
        if not self.account_limiter:
            return

        # Parse JSON body to extract email
        try:
            body = await self._safe_parse_json(request)
        except json.JSONDecodeError:
            logger.warning(
                "Invalid JSON in request body",
                extra={"endpoint": self.endpoint_identifier, "client_ip": client_ip},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in request body",
            )
        except Exception as err:
            logger.warning(
                "Failed to parse request body",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "client_ip": client_ip,
                    "error": str(err),
                    "error_type": type(err).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse request body: {str(err)}",
            )

        email = body.get(self.email_field_name)

        if self.require_email and not email:
            logger.warning(
                "Missing required email field",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "client_ip": client_ip,
                    "field_name": self.email_field_name,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: '{self.email_field_name}'",
            )

        if not email:
            # Email not present – no account-based limiting applied
            logger.debug(
                "No email provided, skipping account-based rate limit",
                extra={"endpoint": self.endpoint_identifier, "client_ip": client_ip},
            )
            return

        normalized_email = RateLimitService.normalize_email(email)
        email_key = RateLimitService.build_email_key(self.endpoint_identifier, normalized_email)

        # Get remaining capacity before consuming
        email_remaining_before = await self.account_limiter.get_remaining(email_key)

        email_allowed = await self.account_limiter.acquire(email_key)

        if not email_allowed:
            logger.warning(
                "Rate limit exceeded for email",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "scope": "email",
                    "identifier": normalized_email,  # Normalised to avoid case leakage
                    "window_size": self.account_limiter.window_size,
                    "limit": self.account_limiter.limit,
                    "remaining_before": email_remaining_before,
                    "allowed": False,
                },
            )
            RateLimitService.raise_email_limit_exceeded()

        logger.debug(
            "Rate limit check passed for email",
            extra={
                "endpoint": self.endpoint_identifier,
                "scope": "email",
                "identifier": normalized_email,
                "window_size": self.account_limiter.window_size,
                "limit": self.account_limiter.limit,
                "remaining_before": email_remaining_before,
                "allowed": True,
            },
        )

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
                return json.loads(body_bytes.decode("utf-8"))
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
        result["ip_remaining"] = await self.ip_limiter.get_remaining(ip_key)

        # Account limit remaining (if applicable)
        if self.account_limiter:
            try:
                body = await self._safe_parse_json(request)
                email = body.get(self.email_field_name)
                if email:
                    normalized_email = RateLimitService.normalize_email(email)
                    email_key = RateLimitService.build_email_key(
                        self.endpoint_identifier, normalized_email
                    )
                    result["account_remaining"] = await self.account_limiter.get_remaining(
                        email_key
                    )
            except Exception:
                # Silently ignore – this is a best-effort method
                pass

        logger.debug(
            "Remaining capacity retrieved",
            extra={
                "endpoint": self.endpoint_identifier,
                "client_ip": client_ip,
                "result": result,
            },
        )

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
            logger.info(
                "Rate limit reset for IP",
                extra={"endpoint": self.endpoint_identifier, "scope": "ip", "identifier": ip},
            )

        if email and self.account_limiter:
            normalized_email = RateLimitService.normalize_email(email)
            email_key = RateLimitService.build_email_key(self.endpoint_identifier, normalized_email)
            await self.account_limiter.reset(email_key)
            logger.info(
                "Rate limit reset for email",
                extra={
                    "endpoint": self.endpoint_identifier,
                    "scope": "email",
                    "identifier": normalized_email,
                },
            )