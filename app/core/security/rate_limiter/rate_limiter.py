# Standard libs
import time
import logging
from typing import Final, Any

# Own Modules
from core.security.rate_limiter.redis_manager import redis_manager

# Module-level logger
logger = logging.getLogger(__name__)


# Sliding Window Log Lua script using Redis Sorted Sets.
# Stores timestamps as scores in a sorted set for precise sliding window calculations.
SLIDING_WINDOW_LOG_LUA: Final[str] = """
local key = KEYS[1]
local window_size = tonumber(ARGV[1])  -- Window size in seconds
local limit = tonumber(ARGV[2])        -- Maximum requests per window
local now = tonumber(ARGV[3])          -- Current timestamp
local requested = tonumber(ARGV[4])    -- Number of requests to count

-- Calculate the cutoff timestamp
local cutoff = now - window_size

-- Remove expired entries (older than window_size)
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)

-- Get current count of requests in the window
local current_count = redis.call('ZCARD', key)

-- Check if the request would exceed the limit
if current_count + requested <= limit then
    -- Add the new request timestamp
    for i = 1, requested do
        redis.call('ZADD', key, now, now .. ':' .. i)
    end

    -- Set expiry on the key (window_size * 2 to ensure it lives long enough)
    redis.call('EXPIRE', key, window_size * 2)

    return 1  -- Access ALLOWED
else
    -- Even on rejection, ensure the key has proper expiry
    redis.call('EXPIRE', key, window_size * 2)
    return 0  -- Access DENIED
end
"""


class SlidingWindowLog:
    """
    A high-performance, distributed Sliding Window Log rate limiter utilizing Redis and Lua.

    The Sliding Window Log algorithm stores timestamps of all requests in a sorted set.
    It counts requests within the last N seconds by removing expired entries and
    counting the remaining ones. This provides precise rate limiting without
    window boundary bursts.

    Key characteristics:
    - High precision (exact window boundaries)
    - No burst at window boundaries
    - Memory O(N) where N is number of requests in window
    - Optimal for scenarios requiring exact rate limiting
    - Higher memory usage than other algorithms

    Optimized for high-concurrency environments by implementing EVALSHA script caching
    and efficient sorted set operations.
    """

    def __init__(self, window_size: float, limit: int):
        """
        Initialize the rate limiter configuration and register the Lua script.

        :param window_size: Size of the sliding window in seconds.
        :param limit: Maximum number of requests allowed in the window.
        """
        self.window_size = window_size
        self.limit = limit

        # Pre-loads the Lua script into Redis memory via 'SCRIPT LOAD'.
        # Subsequent invocations transparently use 'EVALSHA' using the 40-character SHA1 hash.
        self._lua_executable: Any = redis_manager.client.register_script(SLIDING_WINDOW_LOG_LUA)

        logger.debug(
            "SlidingWindowLog initialised",
            extra={
                "window_size": window_size,
                "limit": limit,
                "lua_sha": self._lua_executable.sha,
            },
        )

    async def acquire(self, search_key: str, tokens: int = 1) -> bool:
        """
        Attempt to add a request timestamp to the sliding window log.

        :param search_key: Unique identifier for the rate-limiting scope.
        :param tokens: Number of tokens/requests to consume (default: 1).
        :return: True if the request is within limits, False if rate-limited.
        """
        time_now = time.time()

        logger.debug(
            "Rate limit acquire attempt",
            extra={
                "key": search_key,
                "window_size": self.window_size,
                "limit": self.limit,
                "tokens": tokens,
                "timestamp": time_now,
            },
        )

        try:
            result = await self._lua_executable(
                keys=[search_key],
                args=[self.window_size, self.limit, time_now, tokens],
            )

            allowed = bool(result)

            if allowed:
                logger.debug(
                    "Rate limit acquire - ALLOWED",
                    extra={
                        "key": search_key,
                        "window_size": self.window_size,
                        "limit": self.limit,
                        "tokens": tokens,
                    },
                )
            else:
                # Log denial at WARNING level – this is a security-relevant event
                logger.warning(
                    "Rate limit acquire - DENIED",
                    extra={
                        "key": search_key,
                        "window_size": self.window_size,
                        "limit": self.limit,
                        "tokens": tokens,
                    },
                )

            return allowed

        except Exception as exc:
            logger.error(
                "Redis error during rate limit acquire",
                extra={
                    "key": search_key,
                    "window_size": self.window_size,
                    "limit": self.limit,
                    "tokens": tokens,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            # Fail open or fail closed? In critical systems, fail closed is safer.
            # Here we choose to allow the request if Redis is down, to avoid blocking users.
            # But you may want to raise an exception instead, depending on your SLA.
            # For now, we log the error and return True (allow) – but this is a design decision.
            # Uncomment the next line if you prefer to fail closed:
            # raise
            return True

    async def reset(self, search_key: str) -> None:
        """
        Manually reset the log for a given key.
        Useful for testing or administrative purposes.

        :param search_key: Unique identifier for the rate-limiting scope.
        """
        logger.info(
            "Rate limit reset requested",
            extra={"key": search_key, "window_size": self.window_size, "limit": self.limit},
        )

        try:
            await redis_manager.client.delete(search_key)
            logger.debug(
                "Rate limit reset completed",
                extra={"key": search_key},
            )
        except Exception as exc:
            logger.error(
                "Redis error during rate limit reset",
                extra={"key": search_key, "error": str(exc), "error_type": type(exc).__name__},
                exc_info=True,
            )
            raise

    async def get_current_count(self, search_key: str) -> int:
        """
        Get the current count of requests in the sliding window.

        :param search_key: Unique identifier for the rate-limiting scope.
        :return: Current count in the sliding window.
        """
        time_now = time.time()
        cutoff = time_now - self.window_size

        try:
            # Remove expired entries and get count
            await redis_manager.client.zremrangebyscore(search_key, 0, cutoff)
            count = await redis_manager.client.zcard(search_key)

            logger.debug(
                "Rate limit current count retrieved",
                extra={
                    "key": search_key,
                    "count": count,
                    "window_size": self.window_size,
                    "cutoff_timestamp": cutoff,
                },
            )

            return count

        except Exception as exc:
            logger.error(
                "Redis error during get_current_count",
                extra={
                    "key": search_key,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            # Return 0 as a safe fallback – but consider raising if you prefer strictness.
            return 0

    async def get_remaining(self, search_key: str) -> int:
        """
        Get the remaining capacity in the sliding window.

        :param search_key: Unique identifier for the rate-limiting scope.
        :return: Remaining requests allowed in the sliding window.
        """
        current_count = await self.get_current_count(search_key)
        remaining = max(0, self.limit - current_count)

        logger.debug(
            "Rate limit remaining capacity",
            extra={
                "key": search_key,
                "current_count": current_count,
                "limit": self.limit,
                "remaining": remaining,
            },
        )

        return remaining

    async def get_oldest_timestamp(self, search_key: str) -> float:
        """
        Get the oldest timestamp in the log.

        :param search_key: Unique identifier for the rate-limiting scope.
        :return: Oldest timestamp in the log, or 0 if empty.
        """
        try:
            oldest = await redis_manager.client.zrange(search_key, 0, 0, withscores=True)
            timestamp = float(oldest[0][1]) if oldest else 0.0

            logger.debug(
                "Rate limit oldest timestamp",
                extra={"key": search_key, "oldest_timestamp": timestamp},
            )

            return timestamp

        except Exception as exc:
            logger.error(
                "Redis error during get_oldest_timestamp",
                extra={"key": search_key, "error": str(exc), "error_type": type(exc).__name__},
                exc_info=True,
            )
            return 0.0

    async def get_newest_timestamp(self, search_key: str) -> float:
        """
        Get the newest timestamp in the log.

        :param search_key: Unique identifier for the rate-limiting scope.
        :return: Newest timestamp in the log, or 0 if empty.
        """
        try:
            newest = await redis_manager.client.zrange(search_key, -1, -1, withscores=True)
            timestamp = float(newest[0][1]) if newest else 0.0

            logger.debug(
                "Rate limit newest timestamp",
                extra={"key": search_key, "newest_timestamp": timestamp},
            )

            return timestamp

        except Exception as exc:
            logger.error(
                "Redis error during get_newest_timestamp",
                extra={"key": search_key, "error": str(exc), "error_type": type(exc).__name__},
                exc_info=True,
            )
            return 0.0