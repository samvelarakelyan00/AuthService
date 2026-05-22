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
