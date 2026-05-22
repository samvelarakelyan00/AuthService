# Standard libs
from typing import Annotated

# Non-Standard libs
# Pydantic
from pydantic import (
    BaseModel, Field,
    AfterValidator, TypeAdapter,
    PostgresDsn, computed_field
)


def validate_postgres_url(v: str) -> str:
    """Allow asyncpg driver but validate as standard PostgresDsn."""
    url_for_validation = v.replace("+asyncpg", "")
    TypeAdapter(PostgresDsn).validate_python(url_for_validation)

    return v


PostgresUrl = Annotated[str, AfterValidator(validate_postgres_url)]


class PostgresSettings(BaseModel):
    DATABASE_URL: PostgresUrl

    POOL_SIZE: int = Field(default=5, ge=1, le=100)
    MAX_OVERFLOW: int = Field(default=10, gt=0, le=50)
    POOL_TIMEOUT: int = Field(default=30, ge=0, le=90)
    POOL_RECYCLE: int = Field(default=3600, ge=0, le=3600 * 5)
    POOL_PRE_PING: bool = True

    @computed_field
    @property
    def sync_url(self) -> str:
        """Useful when you need SQLAlchemy sync engine (e.g. Alembic migrations)."""
        return self.DATABASE_URL.replace("+asyncpg", "")
