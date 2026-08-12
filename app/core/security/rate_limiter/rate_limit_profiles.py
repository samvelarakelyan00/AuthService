from core.security.rate_limiter.rate_limiter import SlidingWindowLog


# =============================================================================
# Default Limiters
# =============================================================================
# General purpose rate limiters for standard endpoints
# 60 requests per 60-second sliding window
DEFAULT_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=60)
DEFAULT_ACCOUNT_LIMITER = SlidingWindowLog(window_size=60.0, limit=60)

# =============================================================================
# Signup Limiters
# =============================================================================
# More restrictive limits for account creation to prevent abuse
# Signup IP: 5 signups per 60-second sliding window
SIGNUP_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=5)
# Signup Email: 2 signups per 60-second sliding window
SIGNUP_EMAIL_LIMITER = SlidingWindowLog(window_size=60.0, limit=2)

# =============================================================================
# Email Verification Limiters
# =============================================================================
# More restrictive limits for email verification to prevent brute-force
# Email Verification IP: 10 attempts per 60-second sliding window
VERIFY_EMAIL_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=10)
# Email Verification Email: 3 attempts per 60-second sliding window
VERIFY_EMAIL_ACCOUNT_LIMITER = SlidingWindowLog(window_size=60.0, limit=3)

# =============================================================================
# Login Limiters
# =============================================================================
# Stricter limits for authentication endpoints to prevent brute force
# Login IP: 3 attempts per 60-second sliding window
LOGIN_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=3)
# Login Email: 3 attempts per 60-second sliding window
LOGIN_EMAIL_LIMITER = SlidingWindowLog(window_size=60.0, limit=3)

# =============================================================================
# Refresh Token Limiters
# =============================================================================
# Stricter limits for /refresh refresh token endpoint to prevent brute force
# Refresh Token IP: 3 attempts per 3-second sliding window
REFRESH_TOKEN_IP_LIMITER = SlidingWindowLog(window_size=3.0, limit=3)
# Refresh Token Email: 3 attempts per 3-second sliding window
REFRESH_TOKEN_EMAIL_LIMITER = SlidingWindowLog(window_size=3.0, limit=3)

# =============================================================================
# Optional: Additional Common Profiles
# =============================================================================
# These can be uncommented and used as needed

# API Rate Limits
# API_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=100)
# API_ACCOUNT_LIMITER = SlidingWindowLog(window_size=60.0, limit=1000)

# Public Endpoint Limits
# PUBLIC_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=30)

# Admin Endpoint Limits (more permissive)
# ADMIN_IP_LIMITER = SlidingWindowLog(window_size=60.0, limit=200)

# High-Security Endpoints (very restrictive)
# SECURE_IP_LIMITER = SlidingWindowLog(window_size=300.0, limit=5)
# SECURE_ACCOUNT_LIMITER = SlidingWindowLog(window_size=300.0, limit=5)

# =============================================================================
# Utility Class for Predefined Window Sizes
# =============================================================================
class WindowSizes:
    """Common window sizes in seconds for reference."""
    SECONDS_1 = 1.0
    SECONDS_5 = 5.0
    SECONDS_15 = 15.0
    SECONDS_30 = 30.0
    MINUTE_1 = 60.0
    MINUTES_5 = 300.0
    MINUTES_15 = 900.0
    MINUTES_30 = 1800.0
    HOUR_1 = 3600.0
    DAY_1 = 86400.0


class RateLimitPresets:
    """
    Pre-defined rate limit configurations for common use cases.
    """

    @staticmethod
    def per_minute(limit: int) -> SlidingWindowLog:
        """Create a rate limiter with per-minute window."""
        return SlidingWindowLog(window_size=WindowSizes.MINUTE_1, limit=limit)

    @staticmethod
    def per_second(limit: int) -> SlidingWindowLog:
        """Create a rate limiter with per-second window."""
        return SlidingWindowLog(window_size=WindowSizes.SECONDS_1, limit=limit)

    @staticmethod
    def per_hour(limit: int) -> SlidingWindowLog:
        """Create a rate limiter with per-hour window."""
        return SlidingWindowLog(window_size=WindowSizes.HOUR_1, limit=limit)

    @staticmethod
    def per_day(limit: int) -> SlidingWindowLog:
        """Create a rate limiter with per-day window."""
        return SlidingWindowLog(window_size=WindowSizes.DAY_1, limit=limit)