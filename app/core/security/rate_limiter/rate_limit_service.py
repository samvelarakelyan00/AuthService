# Non-Standard libs
from fastapi import (
    status,
    Request,
    HTTPException
)


class RateLimitService:
    ALGORITHM_NAME = "Sliding Window Log"

    @staticmethod
    def extract_client_ip(request: Request) -> str:
        """
        Extracts the genuine client IP address behind proxies.
        Safeguards against header-spoofing by enforcing trusted proxy lookups.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")

        if forwarded_for:
            # The first IP in the list is the original client, subsequent ones are proxy hops
            return forwarded_for.split(",")[0].strip()

        # Cloudflare specific optimization if applicable
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip

        return request.client.host if request.client else "127.0.0.1"

    @staticmethod
    def normalize_email(email: str) -> str:
        """
        Normalize email address by stripping whitespace and converting to lowercase.
        This ensures consistent rate limiting regardless of email case variations.
        """
        return email.strip().lower()

    @staticmethod
    def build_ip_key(endpoint: str, ip: str) -> str:
        """
        Build a Redis key for IP-based rate limiting.

        :param endpoint: Endpoint identifier (e.g., 'login', 'signup')
        :param ip: Client IP address
        :return: Redis key string
        """
        return f"rate:{endpoint}:ip:{ip}"

    @classmethod
    def build_email_key(cls, endpoint: str, email: str) -> str:
        """
        Build a Redis key for email-based rate limiting.
        Automatically normalizes the email address.

        :param endpoint: Endpoint identifier (e.g., 'login', 'signup')
        :param email: Email address to normalize and use as key
        :return: Redis key string
        """
        email = cls.normalize_email(email)
        return f"rate:{endpoint}:email:{email}"

    @classmethod
    def raise_ip_limit_exceeded(cls) -> None:
        """
        Raise HTTP 429 exception for IP-based rate limit exceeded.
        Uses the configured algorithm name in the error message.
        """
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{cls.ALGORITHM_NAME} -> Your IP limit exceeded; please try again later!"
        )

    @classmethod
    def raise_email_limit_exceeded(cls) -> None:
        """
        Raise HTTP 429 exception for email-based rate limit exceeded.
        Uses the configured algorithm name in the error message.
        """
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{cls.ALGORITHM_NAME} -> Your email limit exceeded; please try again later!"
        )

    @classmethod
    def raise_custom_limit_exceeded(cls, resource: str) -> None:
        """
        Raise HTTP 429 exception for custom resource rate limit exceeded.

        :param resource: Name of the resource that exceeded the limit
        """
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{cls.ALGORITHM_NAME} -> Your {resource} limit exceeded; please try again later!"
        )

    @staticmethod
    def extract_request_metadata(request: Request) -> dict:
        """
        Extract useful metadata from the request for logging or debugging.

        :param request: FastAPI Request object
        :return: Dictionary with request metadata
        """
        return {
            "client_ip": RateLimitService.extract_client_ip(request),
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "content_type": request.headers.get("Content-Type", "unknown"),
        }