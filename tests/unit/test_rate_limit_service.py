# Non-Standard libs
import pytest
from fastapi import HTTPException

# Own Modules
from core.security.rate_limiter.rate_limit_service import RateLimitService


# --------------------------------------------------------------------------------------
# Email Normalization
# --------------------------------------------------------------------------------------
def test_normalize_email_lowercases() -> None:
    result = RateLimitService.normalize_email("John.Doe@GMAIL.COM")
    assert result == "john.doe@gmail.com"


def test_normalize_email_strips_whitespace() -> None:
    result = RateLimitService.normalize_email("   test@gmail.com   ")
    assert result == "test@gmail.com"


def test_normalize_email_strips_and_lowercases() -> None:
    result = RateLimitService.normalize_email("   TeSt@GMAIL.Com   ")
    assert result == "test@gmail.com"


# --------------------------------------------------------------------------------------
# IP Key Generation
# --------------------------------------------------------------------------------------
def test_build_ip_key_login() -> None:
    result = RateLimitService.build_ip_key(
        endpoint="login",
        ip="127.0.0.1"
    )
    assert result == "rate:login:ip:127.0.0.1"


def test_build_ip_key_signup() -> None:
    result = RateLimitService.build_ip_key(
        endpoint="signup",
        ip="192.168.1.10"
    )
    assert result == "rate:signup:ip:192.168.1.10"


def test_build_ip_key_with_special_characters() -> None:
    result = RateLimitService.build_ip_key(
        endpoint="api",
        ip="2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    )
    assert result == "rate:api:ip:2001:0db8:85a3:0000:0000:8a2e:0370:7334"


# --------------------------------------------------------------------------------------
# Email Key Generation
# --------------------------------------------------------------------------------------
def test_build_email_key_format() -> None:
    result = RateLimitService.build_email_key(
        endpoint="login",
        email="test@gmail.com"
    )
    assert result == "rate:login:email:test@gmail.com"


def test_build_email_key_normalizes_email() -> None:
    result = RateLimitService.build_email_key(
        endpoint="login",
        email="   TeSt@GMAIL.COM   "
    )
    assert result == "rate:login:email:test@gmail.com"


def test_build_email_key_with_plus_addressing() -> None:
    result = RateLimitService.build_email_key(
        endpoint="signup",
        email="test+alias@gmail.com"
    )
    assert result == "rate:signup:email:test+alias@gmail.com"


# --------------------------------------------------------------------------------------
# HTTP Exceptions
# --------------------------------------------------------------------------------------
def test_raise_ip_limit_raises_http_exception() -> None:
    with pytest.raises(HTTPException) as exc:
        RateLimitService.raise_ip_limit_exceeded()

    assert exc.value.status_code == 429
    assert exc.value.detail == "Sliding Window Log -> Your IP limit exceeded; please try again later!"


def test_raise_email_limit_raises_http_exception() -> None:
    with pytest.raises(HTTPException) as exc:
        RateLimitService.raise_email_limit_exceeded()

    assert exc.value.status_code == 429
    assert exc.value.detail == "Sliding Window Log -> Your email limit exceeded; please try again later!"


def test_raise_custom_limit_exceeded() -> None:
    with pytest.raises(HTTPException) as exc:
        RateLimitService.raise_custom_limit_exceeded("API")

    assert exc.value.status_code == 429
    assert exc.value.detail == "Sliding Window Log -> Your API limit exceeded; please try again later!"


def test_raise_custom_limit_with_different_resource() -> None:
    with pytest.raises(HTTPException) as exc:
        RateLimitService.raise_custom_limit_exceeded("Download")

    assert exc.value.status_code == 429
    assert exc.value.detail == "Sliding Window Log -> Your Download limit exceeded; please try again later!"


# --------------------------------------------------------------------------------------
# Request Metadata Extraction
# --------------------------------------------------------------------------------------
def test_extract_request_metadata_returns_client_ip() -> None:
    from fastapi import Request
    from starlette.datastructures import Headers

    mock_request = Request({
        "type": "http",
        "path": "/api/v1/auth/login",
        "method": "POST",
        "headers": Headers({"x-forwarded-for": "192.168.1.1"}).raw,
        "client": ("127.0.0.1", 8000)
    })

    metadata = RateLimitService.extract_request_metadata(mock_request)
    assert metadata["client_ip"] == "192.168.1.1"


def test_extract_request_metadata_returns_path_and_method() -> None:
    from fastapi import Request
    from starlette.datastructures import Headers

    mock_request = Request({
        "type": "http",
        "path": "/api/v1/auth/login",
        "method": "POST",
        "headers": Headers({}).raw,
        "client": ("127.0.0.1", 8000)
    })

    metadata = RateLimitService.extract_request_metadata(mock_request)
    assert metadata["path"] == "/api/v1/auth/login"
    assert metadata["method"] == "POST"


def test_extract_request_metadata_handles_missing_headers() -> None:
    from fastapi import Request
    from starlette.datastructures import Headers

    mock_request = Request({
        "type": "http",
        "path": "/api/v1/auth/login",
        "method": "POST",
        "headers": Headers({}).raw,
        "client": ("127.0.0.1", 8000)
    })

    metadata = RateLimitService.extract_request_metadata(mock_request)
    assert metadata["user_agent"] == "unknown"
    assert metadata["content_type"] == "unknown"


def test_extract_request_metadata_uses_fallback_ip() -> None:
    from fastapi import Request
    from starlette.datastructures import Headers

    mock_request = Request({
        "type": "http",
        "path": "/api/v1/auth/login",
        "method": "POST",
        "headers": Headers({}).raw,
        "client": None
    })

    metadata = RateLimitService.extract_request_metadata(mock_request)
    assert metadata["client_ip"] == "127.0.0.1"


def test_extract_request_metadata_handles_cloudflare_header() -> None:
    from fastapi import Request
    from starlette.datastructures import Headers

    mock_request = Request({
        "type": "http",
        "path": "/api/v1/auth/login",
        "method": "POST",
        "headers": Headers({"cf-connecting-ip": "198.51.100.42"}).raw,
        "client": ("1.2.3.4", 8000)
    })

    metadata = RateLimitService.extract_request_metadata(mock_request)
    assert metadata["client_ip"] == "198.51.100.42"