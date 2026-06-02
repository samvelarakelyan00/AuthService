# Non-Standard libs
from pydantic import BaseModel, Field


class PasswordSettings(BaseModel):
    """
    Structured validation namespace for cryptographic password hashing parameters.
    """
    ARGON2_MEMORY_COST: int = Field(default=65536, ge=2048, le=1048576)
    ARGON2_TIME_COST: int = Field(default=3, ge=1, le=50)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1, le=64)
