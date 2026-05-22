# Standard libs
# ...

# Non-Standard libs
# FastAPI
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

# SqlAlchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
# Redis
import redis.asyncio as aioredis
# JWT
import jwt

# Own Modules
from core.security import Security  # Imported for structural type hinting
from core.settings import settings
from models.users import User
from schemas.user_schemas import (
    UserCreateSchema,
    UserOutSchema,
    UserLoginSchema
)
from schemas.token_schemas import TokenOutSchema


class AuthService:
    """
    Orchestrates authentication workflows including user registration, login sessions,
    token rotation lifecycle management, and secure multi-device termination.
    """
    def __init__(self, db: AsyncSession, redis: aioredis.Redis, security: Security) -> None:
        self.db = db
        self.redis = redis
        self.security = security

    async def signup(self, user_create_data: UserCreateSchema) -> UserOutSchema:
        """
        Registers a new user record into the database.
        Offloads the computational weight of Argon2ID password hashing to a background threadpool.
        """
        # Execute password hashing off the main event loop to keep the async loop non-blocking
        hashed_password = await run_in_threadpool(
            self.security.passwords.hash,
            user_create_data.plain_password
        )

        stmt = (
            insert(User)
            .values(
                username=user_create_data.username,
                email=user_create_data.email,
                hashed_password=hashed_password
            )
            .returning(User)
        )

        result = await self.db.execute(stmt)
        new_user_model = result.scalar_one()

        await self.db.commit()

        return UserOutSchema.model_validate(new_user_model)

    async def login(self, user_login_data: UserLoginSchema) -> TokenOutSchema:
        """
        Validates user identity and provisions a fully-formed JWT access and refresh token pair.
        Saves the refresh session metadata in a Redis cache whitelist for rotation Tracking.
        """
        stmt = select(User).where(User.email == user_login_data.email)
        result = await self.db.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Offload intensive Argon2 validation away from the async primary loop
        password_correct = await run_in_threadpool(
            self.security.passwords.verify,
            user_login_data.password,
            user.hashed_password
        )
        if not password_correct:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user_id = str(user.user_id)

        # Generate tokens utilizing the static TokenSecurityManager layout
        access_data = self.security.tokens.create_access_token(user_id=user_id)
        refresh_data = self.security.tokens.create_refresh_token(user_id=user_id)

        # Establish an active whitelist status record inside Redis
        redis_key = f"auth:refresh:{user_id}:{refresh_data['jti']}"
        await self.redis.set(redis_key, "active", ex=refresh_data["ttl_seconds"])

        return TokenOutSchema(
            access_token=access_data["token"],
            refresh_token=refresh_data["token"]
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenOutSchema:
        """
        Executes a secure refresh token rotation flow.
        Implements a atomic Redis pipeline grace period to safely mitigate front-end concurrency
        race conditions when multiple requests hit the server simultaneously.
        """
        try:
            payload = self.security.tokens.verify_token(refresh_token_str, expected_type="refresh")
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))

        user_id = payload.get("sub")
        token_jti = payload.get("jti")

        redis_key = f"auth:refresh:{user_id}:{token_jti}"
        token_status = await self.redis.get(redis_key)

        if not token_status:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired"
            )

        # Block duplicate reuse if the short-lived grace period has fully concluded
        if token_status == "rotated":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token already rotated. Please reuse the new pair."
            )

        # Generate fresh authorization vectors
        new_access_data = self.security.tokens.create_access_token(user_id=user_id)
        new_refresh_data = self.security.tokens.create_refresh_token(user_id=user_id)

        new_redis_key = f"auth:refresh:{user_id}:{new_refresh_data['jti']}"

        # Atomic Pipeline Execution: Transitions the old key state to avoid client-side drops
        async with self.redis.pipeline(transaction=True) as pipe:
            # Grant a 15-second grace period for ongoing parallel browser requests to resolve
            await pipe.set(redis_key, "rotated", ex=15)
            await pipe.set(new_redis_key, "active", ex=new_refresh_data["ttl_seconds"])
            await pipe.execute()

        return TokenOutSchema(
            access_token=new_access_data["token"],
            refresh_token=new_refresh_data["token"]
        )

    async def logout(self, refresh_token_str: str) -> None:
        """
        Performs an idempotent session logout.
        Bypasses expiration restrictions to strip session variables from Redis
        even if a signature has passed its valid lifetime duration.
        """
        try:
            # First attempt a strict signature and lifetime check
            payload = self.security.tokens.verify_token(refresh_token_str, expected_type="refresh")
            user_id = payload.get("sub")
            token_jti = payload.get("jti")
        except ValueError as err:
            # If the signature is intact but simply expired, force decrypt to locate the JTI mapping
            if "expired" in str(err):
                try:
                    payload = jwt.decode(
                        refresh_token_str,
                        key=settings.tokens.SECRET_KEY.get_secret_value(),
                        algorithms=[settings.tokens.ALGORITHM],
                        options={"verify_exp": False}  # Bypass expiration check to fetch identifiers
                    )
                    user_id = payload.get("sub")
                    token_jti = payload.get("jti")
                except Exception:
                    # Terminate if the cryptographic envelope hash is corrupted
                    return
            else:
                return

        # Purge target whitelist entry completely from active cache memory
        if user_id and token_jti:
            redis_key = f"auth:refresh:{user_id}:{token_jti}"
            await self.redis.delete(redis_key)
            print(f"Session auth:refresh:{user_id}:{token_jti} successfully evicted via Logout.")

    async def logout_from_all_devices(self, user_id: str) -> None:
        """
        Scans and terminates all active token whitelists matching the targeted user space.
        """
        pattern = f"auth:refresh:{user_id}:*"
        cursor = 0

        while True:
            # Paginate through keys safely using non-blocking SCAN clusters
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

        print(f"All active infrastructure sessions for user {user_id} have been invalidated.")
