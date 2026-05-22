# Standard libs
# ...

# Non-Standard libs
# Pydantic
from pydantic import BaseModel, SecretStr


class TokenSettings(BaseModel):
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_TYPE: str = "access"
    REFRESH_TOKEN_TYPE: str = "refresh"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 60 MIN * 24 HOURS * 30 DAYS (1 month by minutes) 43.200
