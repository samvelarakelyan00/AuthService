# Standard libs
import abc
import time
import logging
from typing import Optional

# Non-Standard libs
from fastapi import Request, HTTPException, status
import redis.asyncio as aioredis


logger = logging.getLogger("security.ratelimit")


class BaseRateLimiter(abc.ABC):
    """
    Abstract Base Class for Rate Limiting Strategies.
    Allows for future architectural shifts (e.g., Token Bucket, Leaky Bucket)
    without breaking FastAPI endpoint route signatures.
    """

    @abc.abstractmethod
    async def __call__(self, request: Request) -> None:
        pass


class SlidingWindowLogAuthLimiter(BaseRateLimiter):
    """
    Production-Grade Composite Multi-Key Sliding Window Log Rate Limiter.

    Protects authentication vectors by tracking individual request counts
    by both network origin IP and targeted account profiles concurrently.
    """

    def __init__(self, times: int, seconds: int, endpoint_tag: str) -> None:
        self.times = times
        self.seconds = seconds
        self.endpoint_tag = endpoint_tag

    async def __call__(self, request: Request) -> None:
        # Fetch the verified active Redis connection mounted on the app state pool
        redis_client: Optional[aioredis.Redis] = getattr(request.app.state, "redis_client", None)
        if not redis_client:
            logger.critical("Configuration Error: RateLimiter executed but request.app.state.redis_client is missing.")
            return  # Fail-open design pattern to keep the app functional if Redis drops out

        # 1. Isolate Network Layer Origin Identification
        client_ip = request.client.host if request.client else "unknown"
        ip_tracking_key = f"rl:ip:{client_ip}:{self.endpoint_tag}"

        # 2. Extract targeted user identity without consuming the request payload buffer stream
        target_account: Optional[str] = None
        if request.method == "POST":
            try:
                # request.json() caches the payload internally, keeping it available for schema validation
                body_payload = await request.json()
                if isinstance(body_payload, dict):
                    # Check common identity mapping labels
                    target_account = body_payload.get("email") or body_payload.get("username")
            except Exception:
                # Fail-silent on body extraction to handle non-JSON or missing payloads gracefully
                pass

        # 3. Evaluate Network Origin Boundary Limits
        await self._process_sliding_window(
            redis=redis_client,
            key=ip_tracking_key,
            limit=self.times,
            window=self.seconds,
            error_message="Too many access requests from this network origin."
        )

        # 4. Evaluate Profile Identity Target Limits (Mitigates Credential Stuffing)
        if target_account:
            clean_account_id = str(target_account).strip().lower()
            account_tracking_key = f"rl:acct:{clean_account_id}:{self.endpoint_tag}"

            await self._process_sliding_window(
                redis=redis_client,
                key=account_tracking_key,
                limit=self.times,
                window=self.seconds,
                error_message="Security lock triggered: Excessive login verification attempts targeting this profile."
            )

    async def _process_sliding_window(
            self, redis: aioredis.Redis, key: str, limit: int, window: int, error_message: str
    ) -> None:
        """
        Executes a precise sliding window log strategy inside an atomic Redis pipeline.
        """
        now = time.time()
        expiration_horizon = now - window

        try:
            async with redis.pipeline(transaction=True) as pipe:
                # Drop tracking log entries that fall outside the sliding window
                pipe.zremrangebyscore(key, 0, expiration_horizon)
                # Count current active entries remaining inside the window scope
                pipe.zcard(key)
                # Log the current unique tracking timestamp hit
                pipe.zadd(key, {f"{now}": now})
                # Set automatic cache expiration to prevent memory leaks
                pipe.expire(key, window)

                # Execute pipeline transaction operations atomically
                _, total_hits_in_window, _, _ = await pipe.execute()

            if total_hits_in_window > limit:
                logger.warning("Rate limit barrier breached for entity tracking key: '%s' [Hits: %d/%d]",
                               key, total_hits_in_window, limit)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_message,
                    headers={"Retry-After": str(window)}
                )

        except HTTPException:
            raise  # Bubble up expected HTTP 429 exceptions to client responses
        except Exception as system_error:
            # Operational Resilience Rule: Never crash user facing routes if the cache architecture drops offline
            logger.error("Rate Limiter system processing exception caught: %s. Allowing access bypass.",
                         str(system_error), exc_info=True)
            return
