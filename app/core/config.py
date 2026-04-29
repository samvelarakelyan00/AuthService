import os
from pathlib import Path
from functools import lru_cache
from typing import Annotated, Literal, Any, Dict, Type, Tuple

from pydantic import (
    BaseModel,
    Field,
    PostgresDsn,
    TypeAdapter,
    AfterValidator,
    computed_field,
    SecretStr,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict
)

import boto3


print(os.getenv("ENV_STATE"))


# =============================================
# 1. BASE DIRECTORY (project root)
# =============================================
BASE_DIR = Path(__file__).resolve().parent.parent  # app/core/config.py → project root


# =============================================
# 2. SHARED VALIDATORS (security + correctness)
# =============================================
def validate_postgres_url(v: str) -> str:
    """Allow asyncpg driver but validate as standard PostgresDsn."""
    url_for_validation = v.replace("+asyncpg", "")
    TypeAdapter(PostgresDsn).validate_python(url_for_validation)
    return v


PostgresUrl = Annotated[str, AfterValidator(validate_postgres_url)]


# =============================================
# 3. LOGICAL BLOCKS (Pure Data Models) — BEST PRACTICE
# =============================================
class DatabaseSettings(BaseModel):
    """All DB-related settings grouped together (OOP separation of concerns)."""
    DATABASE_URL: PostgresUrl
    POOL_SIZE: int = Field(default=5, ge=1, le=100)
    MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    POOL_TIMEOUT: int = Field(default=30, ge=0)
    POOL_RECYCLE: int = Field(default=3600, ge=0)
    POOL_PRE_PING: bool = True

    @computed_field
    @property
    def sync_url(self) -> str:
        """Useful when you need SQLAlchemy sync engine (e.g. Alembic migrations)."""
        return self.DATABASE_URL.replace("+asyncpg", "")


class TokenSettings(BaseModel):
    """JWT / Auth settings grouped together."""
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


# =============================================
# 4. BASE SETTINGS (flat env vars + modular accessors)
# =============================================
class GlobalSettings(BaseSettings):
    """Base class — never instantiated directly except by factory."""
    ENV_STATE: Literal["", "local", "prod", "test"] = Field(
        default="local",
        validation_alias="ENV_STATE",
    )

    # === Database settings (flat for simple .env files) ===
    DATABASE_URL: PostgresUrl = Field(..., validation_alias="DATABASE_URL")
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True

    # === Security / Token settings ===
    SECRET_KEY: SecretStr = Field(..., validation_alias="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_file=None,           # No file by default — only OS env vars
        env_file_encoding="utf-8",
    )

    # ================ MODULAR ACCESSORS (your excellent pattern) ================
    @computed_field
    @property
    def db(self) -> DatabaseSettings:
        """settings.db.DATABASE_URL, settings.db.sync_url etc."""
        return DatabaseSettings(
            DATABASE_URL=self.DATABASE_URL,
            POOL_SIZE=self.POOL_SIZE,
            MAX_OVERFLOW=self.MAX_OVERFLOW,
            POOL_TIMEOUT=self.POOL_TIMEOUT,
            POOL_RECYCLE=self.POOL_RECYCLE,
            POOL_PRE_PING=self.POOL_PRE_PING,
        )

    @computed_field
    @property
    def tokens(self) -> TokenSettings:
        """settings.tokens.SECRET_KEY etc."""
        return TokenSettings(
            SECRET_KEY=self.SECRET_KEY,
            ALGORITHM=self.ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES=self.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

# =============================================
# 5. ENVIRONMENT-SPECIFIC SETTINGS (the magic)
# =============================================
class LocalSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "../.env"),
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8",
    )


class SSMSettingsSource(PydanticBaseSettingsSource):
    """
    Источник настроек, который подтягивает данные из AWS SSM Parameter Store.
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        # Инициализируем клиент один раз при создании источника
        self.ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.env_state = os.getenv("ENV_STATE", None)
        # self.prefix = f"/my-app/{self.env_state}/"
        self.prefix = "/"

    def get_field_value(self, field, field_name):
        # Этот метод обязателен для абстрактного класса,
        # но так как мы переопределяем __call__, он не будет использоваться напрямую.
        return None

    def get_parameters_from_ssm(self) -> Dict[str, Any]:
        if self.env_state == "local" or self.env_state is None:  # Не ходим в AWS на локалке
            return {}

        try:
            params = {}
            paginator = self.ssm.get_paginator('get_parameters_by_path')
            for page in paginator.paginate(Path=self.prefix, WithDecryption=True):
                for p in page['Parameters']:
                    # Из /my-app/prod/DATABASE_URL берем только DATABASE_URL
                    key = p['Name'].replace(self.prefix, "")
                    params[key] = p['Value']
            return params
        except Exception as e:
            print(f"AWS SSM Error: {e}")
            return {}

    def __call__(self) -> Dict[str, Any]:
        """Этот метод вызывается Pydantic при сборке конфига."""
        return self.get_parameters_from_ssm()


class ProdSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # Приоритет: Код -> Env Vars -> AWS SSM -> .env
        return init_settings, env_settings, SSMSettingsSource(settings_cls), dotenv_settings


class TestSettings(GlobalSettings):
    """Testing (pytest, CI) — loads .env.test"""
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "../.env.test"),
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8",
    )


# =============================================
# 6. FACTORY — AUTOMATIC ENVIRONMENT SWITCHING (world-best)
# =============================================
@lru_cache(maxsize=1)
def get_settings() -> GlobalSettings:
    """Single source of truth. Cached for performance."""
    env_state = os.getenv("ENV_STATE", "local").lower().strip()

    if env_state == "local":
        return LocalSettings()

    elif env_state == "prod":
        # Передаем их как именованные аргументы.
        # Pydantic приоритезирует аргументы конструктора выше, чем .env файлы.
        return ProdSettings()

    elif env_state == "test":
        return TestSettings()

    else:
        raise ValueError(
            f"Invalid ENV_STATE={env_state}. "
            "Must be one of: local, prod, test"
        )

# Global instance used everywhere in your app
settings = get_settings()
print(settings)
print(os.getenv("ENV_STATE"))
