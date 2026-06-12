# Standard libs
# ...

# Non-Standard libs
# Pydantic
from pydantic import BaseModel, Field


class RedisSettings(BaseModel):
    HOST: str
    PORT: int = 6379
    DB: int = 0
    MAX_CONNECTIONS: int = Field(default=50, ge=1, le=500)

    # === Security: Rate Limiting Windows ===
    # Strict limits on account creation to prevent mass spam registrations
    SIGNUP_LIMIT_TIMES: int = Field(default=3, ge=1)
    SIGNUP_LIMIT_SECONDS: int = Field(default=3600, ge=1)  # 3 registrations per hour

    # Precise bounds on credential verification to stop brute force/stuffing attacks
    LOGIN_LIMIT_TIMES: int = Field(default=5, ge=1)
    LOGIN_LIMIT_SECONDS: int = Field(default=60, ge=1)  # 5 attempts per minute

    # Bounds on session token regeneration routes
    REFRESH_LIMIT_TIMES: int = Field(default=10, ge=1)
    REFRESH_LIMIT_SECONDS: int = Field(default=60, ge=1)  # 10 refreshes per minute