# === Standard libs ===
import datetime
import uuid
from typing import Dict, Any

# === Non-Standard libs ===
import jwt

# === Own Modules ===
from core.settings import settings


class TokenSecurityManager:
    """
    Handles completely stateless JSON Web Token (JWT) lifecycle operations.
    All methods are marked as static as they interact purely with external arguments
    and global configurations rather than internal instance states.
    """
    @staticmethod
    def create_token(user_id: str, expire_minutes: int, token_type: str) -> Dict[str, Any]:
        """Assembles, signs, and generates a structured JWT cryptographic payload token."""
        now = datetime.datetime.now(datetime.UTC)
        expire = now + datetime.timedelta(minutes=expire_minutes)
        token_jti = str(uuid.uuid4())
        ttl_seconds = int(expire_minutes * 60)

        payload = {
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "sub": str(user_id),
            "token_type": token_type,
            "jti": token_jti
        }

        token = jwt.encode(
            payload=payload,
            key=settings.tokens.SECRET_KEY.get_secret_value(),
            algorithm=settings.tokens.ALGORITHM
        )

        return {
            "token": token,
            "jti": token_jti,
            "ttl_seconds": ttl_seconds
        }

    @staticmethod
    def create_access_token(user_id: str) -> Dict[str, Any]:
        """Generates a short-lived access authorization token wrapper."""
        return TokenSecurityManager.create_token(
            user_id=user_id,
            expire_minutes=settings.tokens.ACCESS_TOKEN_EXPIRE_MINUTES,
            token_type=settings.tokens.ACCESS_TOKEN_TYPE,
        )

    @staticmethod
    def create_refresh_token(user_id: str) -> Dict[str, Any]:
        """Generates a long-lived session renewal token wrapper."""
        return TokenSecurityManager.create_token(
            user_id=user_id,
            expire_minutes=settings.tokens.REFRESH_TOKEN_EXPIRE_MINUTES,
            token_type=settings.tokens.REFRESH_TOKEN_TYPE,
        )

    @staticmethod
    def verify_token(token: str, expected_type: str) -> Dict[str, Any]:
        """
        Decodes, cryptographically crypt-verifies, and validates an incoming JWT's payload signature.
        Raises:
            ValueError: On payload signature breach, expiration, or type mismatch.
        """
        try:
            payload = jwt.decode(
                token,
                key=settings.tokens.SECRET_KEY.get_secret_value(),
                algorithms=[settings.tokens.ALGORITHM]
            )

            if payload.get("token_type") != expected_type:
                raise ValueError("Invalid token type mapping context")

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token signature validation breached: Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Token validation breach: Signature processing integrity error")