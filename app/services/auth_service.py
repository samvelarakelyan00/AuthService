# Standard libs
import logging

# Non-Standard libs
# FastAPI
from fastapi import HTTPException, status, Response
from fastapi.concurrency import run_in_threadpool
# SqlAlchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError
# Redis
import redis.asyncio as aioredis
# JWT
import jwt

# Own Modules
from core.security import Security
from core.settings import settings
from models.users import User
from schemas.user_schemas import (
    UserCreateSchema,
    UserOutSchema,
    UserLoginSchema
)
from schemas.token_schemas import TokenOutSchema

# Instantiate isolated service tracer bound to this module namespace
logger = logging.getLogger(__name__)


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
        Handles database integrity violations securely.
        """
        logger.info("Executing registration workflow for identity email: '%s'", user_create_data.email)

        logger.debug("Offloading Argon2ID password hashing to run_in_threadpool...")
        hashed_password = await run_in_threadpool(
            self.security.passwords.hash,
            user_create_data.plain_password
        )
        logger.debug("Password hashing execution completed successfully.")

        stmt = (
            insert(User)
            .values(
                username=user_create_data.username,
                email=user_create_data.email,
                hashed_password=hashed_password
            )
            .returning(User)
        )

        logger.debug("Executing PostgreSQL database insert query statement.")
        try:
            result = await self.db.execute(stmt)
            new_user_model = result.scalar_one()
            logger.debug("Database insert successful. Generated user identity primary key: '%s'",
                         new_user_model.user_id)

            logger.debug("Committing database transaction state.")
            await self.db.commit()
            logger.debug("Database transaction commit finalized.")

        except IntegrityError as exc:
            logger.warning(
                "Registration conflict: Username or email already exists. Details: %s",
                str(exc.orig)
            )
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered."
            )

        logger.info("User successfully created with assigned ID: '%s'", new_user_model.user_id)
        return UserOutSchema.model_validate(new_user_model)

    async def login(self, user_login_data: UserLoginSchema, response: Response) -> TokenOutSchema:
        """
        Validates user identity and provisions a fully-formed JWT access and refresh token pair.
        Saves the refresh session metadata in a Redis cache whitelist for rotation tracking.
        Injects the refresh token into an HttpOnly, Secure cookie to mitigate XSS vulnerabilities.
        """
        logger.info("Processing login vector authentication request for email: '%s'", user_login_data.email)

        stmt = select(User).where(User.email == user_login_data.email)
        logger.debug("Querying user record from database matching email filter.")
        result = await self.db.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        if user is None:
            logger.warning("Authentication failed: Identity matching email '%s' not found.", user_login_data.email)

            logger.debug("Executing dummy Argon2 verification to mitigate timing attack vectors...")
            dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$dGVzdHBhc3N3b3Jk"
            await run_in_threadpool(
                self.security.passwords.verify,
                user_login_data.password,
                dummy_hash
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        logger.debug("User record found. Offloading Argon2 verification to run_in_threadpool...")
        password_correct = await run_in_threadpool(
            self.security.passwords.verify,
            user_login_data.password,
            user.hashed_password
        )
        logger.debug("Argon2 verification thread evaluation completed with result: '%s'", password_correct)

        if not password_correct:
            logger.warning("Authentication failed: Invalid credentials input for email '%s'.", user_login_data.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user_id = str(user.user_id)

        logger.debug("Generating cryptographically signed JWT keys via TokenSecurityManager.")
        access_data = self.security.tokens.create_access_token(user_id=user_id)
        refresh_data = self.security.tokens.create_refresh_token(user_id=user_id)
        logger.debug("JWT Access and Refresh packages provisioned. Refresh JTI: '%s'", refresh_data["jti"])

        # Establish an active whitelist status record inside Redis
        redis_key = f"auth:refresh:{user_id}:{refresh_data['jti']}"
        logger.debug("Writing token status validation key to Redis cache layer: '%s'", redis_key)
        await self.redis.set(redis_key, "active", ex=refresh_data["ttl_seconds"])
        logger.debug("Redis state mutation finalized with expiration TTL set to %d seconds.",
                     refresh_data["ttl_seconds"])

        logger.debug("Injecting refresh token into HttpOnly response cookie headers.")
        # Check environment strictly via settings.ENV_STATE
        is_production = settings.ENV_STATE == "prod"

        response.set_cookie(
            key="refresh_token",
            value=refresh_data["token"],
            httponly=True,
            secure=is_production,  # True only if env is 'prod'
            samesite="lax",
            max_age=refresh_data["ttl_seconds"],
            path="/",
        )
        logger.debug("Refresh token cookie parameters configured successfully.")

        logger.info("Session successfully authorized. Access token returned and Refresh cookie set for User ID '%s'.",
                    user_id)

        return TokenOutSchema(
            access_token=access_data["token"]
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenOutSchema:
        """
        Executes a secure refresh token rotation flow.
        Implements a atomic Redis pipeline grace period to safely mitigate front-end concurrency
        race conditions when multiple requests hit the server simultaneously.
        """
        logger.debug("Received request to rotate refresh token vectors.")
        try:
            logger.debug("Validating token signature package and checking expiration bounds.")
            payload = self.security.tokens.verify_token(refresh_token_str, expected_type="refresh")
        except ValueError as err:
            logger.warning("Token rotation aborted: Signature validation failed with detail: '%s'", str(err))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))

        user_id = payload.get("sub")
        token_jti = payload.get("jti")
        logger.debug("Token envelope parsed successfully. Extracted User ID: '%s', JTI: '%s'", user_id, token_jti)

        redis_key = f"auth:refresh:{user_id}:{token_jti}"
        logger.debug("Checking active database state whitelist inside Redis using key: '%s'", redis_key)
        token_status = await self.redis.get(redis_key)
        logger.debug("Redis whitelist check returned raw session state status: '%s'", token_status)

        if not token_status:
            logger.warning("Token rotation aborted: Whitelist record missing or expired in cache for JTI '%s'.",
                           token_jti)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired"
            )

        # Block duplicate reuse if the short-lived grace period has fully concluded
        if token_status == "rotated":
            logger.critical(
                "Security Warning: Detected potential token reuse attempt on already rotated JTI '%s' for User ID '%s'!",
                token_jti, user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token already rotated. Please reuse the new pair."
            )

        logger.debug("Generating target authorization child keys for rotation flow.")
        # Generate fresh authorization vectors
        new_access_data = self.security.tokens.create_access_token(user_id=user_id)
        new_refresh_data = self.security.tokens.create_refresh_token(user_id=user_id)

        new_redis_key = f"auth:refresh:{user_id}:{new_refresh_data['jti']}"
        logger.debug("Constructed new child storage registration key target: '%s'", new_redis_key)

        logger.debug("Opening atomic Redis transaction pipeline environment.")
        # Atomic Pipeline Execution: Transitions the old key state to avoid client-side drops
        async with self.redis.pipeline(transaction=True) as pipe:
            # Grant a 15-second grace period for ongoing parallel browser requests to resolve
            await pipe.set(redis_key, "rotated", ex=15)
            await pipe.set(new_redis_key, "active", ex=new_refresh_data["ttl_seconds"])
            logger.debug("Executing transaction instructions inside Redis server pipeline...")
            await pipe.execute()
        logger.debug("Redis pipeline operations completed and verified.")

        logger.info("Token rotation completed. Shifted session from parent JTI '%s' to child JTI '%s' for User '%s'.",
                    token_jti, new_refresh_data['jti'], user_id)
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
        logger.debug("Executing manual session explicit logout pipeline.")
        try:
            logger.debug("Analyzing cryptographic integrity bounds for token verification.")
            # First attempt a strict signature and lifetime check
            payload = self.security.tokens.verify_token(refresh_token_str, expected_type="refresh")
            user_id = payload.get("sub")
            token_jti = payload.get("jti")
        except ValueError as err:
            # If the signature is intact but simply expired, force decrypt to locate the JTI mapping
            if "expired" in str(err):
                logger.debug("Logout token expired. Bypassing timeline evaluation to perform database cache eviction.")
                try:
                    payload = jwt.decode(
                        refresh_token_str,
                        key=settings.tokens.SECRET_KEY.get_secret_value(),
                        algorithms=[settings.tokens.ALGORITHM],
                        options={"verify_exp": False}  # Bypass expiration check to fetch identifiers
                    )
                    user_id = payload.get("sub")
                    token_jti = payload.get("jti")
                    logger.debug("Forced signature decoding successful. Extracted User ID: '%s', JTI: '%s'", user_id,
                                 token_jti)
                except Exception as decode_error:
                    logger.warning("Logout termination aborted: Cryptographic envelope corrupt. Error: '%s'",
                                   str(decode_error))
                    return
            else:
                logger.warning("Logout signature check encountered invalid parameters: '%s'", str(err))
                return

        # Purge target whitelist entry completely from active cache memory
        if user_id and token_jti:
            redis_key = f"auth:refresh:{user_id}:{token_jti}"
            logger.debug("Evicting active session key identifier from Redis cache mapping: '%s'", redis_key)
            await self.redis.delete(redis_key)
            logger.info("Session context 'auth:refresh:%s:%s' successfully evicted via manual user Logout.", user_id,
                        token_jti)

    async def logout_from_all_devices(self, user_id: str) -> None:
        """
        Scans and terminates all active token whitelists matching the targeted user space.
        """
        logger.warning("Initiating multi-device forced termination sequence for User ID: '%s'", user_id)
        pattern = f"auth:refresh:{user_id}:*"
        cursor = 0
        total_evicted_keys = 0
        logger.debug("Preparing to scan key spaces using cursor match pattern: '%s'", pattern)

        while True:
            logger.debug("Executing asynchronous SCAN cluster lookup at cursor offset position: %d", cursor)
            # Paginate through keys safely using non-blocking SCAN clusters
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                logger.debug("SCAN match segment found. Bulk deleting keys: %s", keys)
                await self.redis.delete(*keys)
                total_evicted_keys += len(keys)

            logger.debug("Next iterative lookup window index calculated at position: %d", cursor)
            if cursor == 0:
                logger.debug("SCAN loops hit absolute memory boundary sequence.")
                break

        logger.info("Multi-device reset complete. Invalidated %d total active session keys for user '%s'.",
                    total_evicted_keys, user_id)
