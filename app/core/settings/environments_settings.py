# Standard libs
from pathlib import Path
from typing import Type, Tuple

# Non-Standard libs
# Pydantic
from pydantic_settings import (
    PydanticBaseSettingsSource,
    BaseSettings, SettingsConfigDict
)

# Own Modules
from .global_settings import GlobalSettings
from .ssm_source_settings import SSMSettingsSource


BASE_DIR = Path(__file__).resolve().parent.parent.parent  # /AuthSerive/app/ → project root


class LocalSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_file= str(BASE_DIR / "../.env"),
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8"
    )


class ProductionSettings(GlobalSettings):
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

        return init_settings, env_settings, SSMSettingsSource(settings_cls), dotenv_settings


class DevelopmentSettings(GlobalSettings):
    """Development — loads .env.dev"""
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "../.env.dev"),
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8",
    )


class TestingSettings(GlobalSettings):
    """Testing (pytest, CI) — loads .env.test"""
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "../.env.test"),
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8",
    )
