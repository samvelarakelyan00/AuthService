# === Standard libs ===
import datetime
import uuid
from typing import Dict, Any

# === Non-Standard libs ===
# password hash/verify
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
# jwt
import jwt

# === Own Modules ===
from core.config import settings


custom_argon2 = Argon2Hasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=4
)

password_hash = PasswordHash((custom_argon2,))


class Security:
    @staticmethod
    def get_password_hash(password: str) -> str:
        return password_hash.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return password_hash.verify(plain_password, hashed_password)

    @classmethod
    def create_token(cls, user_id: str, expire_minutes: int, token_type: str) -> Dict[str, Any]:
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

    @classmethod
    def create_access_token(cls, user_id: str) -> Dict[str, Any]:
        return cls.create_token(
            user_id=user_id,
            expire_minutes=settings.tokens.ACCESS_TOKEN_EXPIRE_MINUTES,
            token_type=settings.tokens.ACCESS_TOKEN_TYPE,
        )

    @classmethod
    def create_refresh_token(cls, user_id: str) -> Dict[str, Any]:
        return cls.create_token(
            user_id=user_id,
            expire_minutes=settings.tokens.REFRESH_TOKEN_EXPIRE_MINUTES,
            token_type=settings.tokens.REFRESH_TOKEN_TYPE,
        )

    @classmethod
    def verify_token(cls, token: str, expected_type: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                key=settings.tokens.SECRET_KEY.get_secret_value(),
                algorithms=[settings.tokens.ALGORITHM]
            )

            if payload.get("token_type") != expected_type:
                raise ValueError("Invalid token type")

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
