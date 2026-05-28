# Standard libs
from pathlib import Path
from typing import Literal

# Non-Standard libs
# Pydantic
from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Own Modules
from .postgres_settings import PostgresUrl, PostgresSettings
from .redis_settings import RedisSettings
from .tokens_settings import TokenSettings
from .logging_settings import LoggingSettings  # NEW LOG MODULE INJECTION


BASE_DIR = Path(__file__).resolve().parent.parent  # /AuthService/app/


class GlobalSettings(BaseSettings):
    """Base class — never instantiated directly except by factory."""
    ENV_STATE: Literal['', 'local', 'dev', 'test', 'prod'] = Field(
        default='local',
        validation_alias='ENV_STATE'
    )

    # === Database settings (flat for simple .env files) ===
    DATABASE_URL: PostgresUrl = Field(..., validation_alias='DATABASE_URL')
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True

    # === Redis settings (flat for simple .env files) ===
    REDIS_HOST: str = Field(default="localhost", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = Field(default=0, validation_alias="REDIS_DB")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, validation_alias="REDIS_MAX_CONNECTIONS")

    # === Security / Token settings ===
    SECRET_KEY: SecretStr = Field(..., validation_alias='SECRET_KEY')
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # === Logging Engine Settings (flat for infrastructure injection) ===
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    LOG_JSON_FORMAT: bool = Field(
        default=False, validation_alias="LOG_JSON_FORMAT"
    )
    LOG_DIR: str = Field(
        default=str(BASE_DIR.parent / "logs"), validation_alias="LOG_DIR"
    )
    LOG_MAX_BYTES: int = Field(default=10485760, validation_alias="LOG_MAX_BYTES")
    LOG_BACKUP_COUNT: int = Field(default=5, validation_alias="LOG_BACKUP_COUNT")

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_file=None,
        env_file_encoding="utf-8"
    )

    # ================ MODULAR ACCESSORS ================
    @computed_field
    @property
    def db(self) -> PostgresSettings:
        return PostgresSettings(
            DATABASE_URL=self.DATABASE_URL,
            POOL_SIZE=self.POOL_SIZE,
            MAX_OVERFLOW=self.MAX_OVERFLOW,
            POOL_TIMEOUT=self.POOL_TIMEOUT,
            POOL_RECYCLE=self.POOL_RECYCLE,
            POOL_PRE_PING=self.POOL_PRE_PING
        )

    @computed_field
    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(
            HOST=self.REDIS_HOST,
            PORT=self.REDIS_PORT,
            DB=self.REDIS_DB,
            MAX_CONNECTIONS=self.REDIS_MAX_CONNECTIONS
        )

    @computed_field
    @property
    def tokens(self) -> TokenSettings:
        return TokenSettings(
            SECRET_KEY=self.SECRET_KEY,
            ALGORITHM=self.ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES=self.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    @computed_field
    @property
    def logging(self) -> LoggingSettings:
        """
        Exposes structured validation namespace to the application context.
        Usage: settings.logging.LOG_LEVEL
        """
        return LoggingSettings(
            LOG_LEVEL=self.LOG_LEVEL,
            LOG_JSON_FORMAT=self.LOG_JSON_FORMAT,
            LOG_DIR=Path(self.LOG_DIR),
            LOG_MAX_BYTES=self.LOG_MAX_BYTES,
            LOG_BACKUP_COUNT=self.LOG_BACKUP_COUNT
        )
