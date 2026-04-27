# === Standard libs ===
import datetime
from typing import Dict, Any

# === Non-Standard libs ===
# password hash/verify
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
# jwt
import jwt

# === Own Modules ===
from core.config import settings
from schemas.token_schemas import (
    AccessTokenPayloadDataSchema
)


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

    @staticmethod
    def create_access_token(user_id: str) -> str:
        expire = (datetime.datetime.now(tz=datetime.UTC) +
                  datetime.timedelta(minutes=settings.tokens.ACCESS_TOKEN_EXPIRE_MINUTES))

        payload = {
            "exp": expire,
            "sub": user_id
        }

        access_token = jwt.encode(
            payload=payload,
            key=settings.tokens.SECRET_KEY.get_secret_value(),
            algorithm=settings.tokens.ALGORITHM
        )

        return access_token

    @staticmethod
    def verify_access_token(access_token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                access_token,
                key=settings.tokens.SECRET_KEY.get_secret_value(),
                algorithms=[settings.tokens.ALGORITHM]
            )

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
