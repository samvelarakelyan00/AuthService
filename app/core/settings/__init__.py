# Standard libs
import os
from functools import lru_cache

# Non-Standard libs
# ...

# Own Modules
from .global_settings import GlobalSettings
from .environments_settings import (
    LocalSettings, ProductionSettings,
    DevelopmentSettings, TestingSettings
)


@lru_cache(maxsize=1)
def get_settings() -> GlobalSettings:
    """
    Single source of truth for application settings.
    Cached for performance to guarantee only a single environmental instance exists.
    """
    env_state = os.getenv("ENV_STATE", "local").strip().lower()

    if env_state == "prod":
        return ProductionSettings()
    elif env_state == "dev":
        return DevelopmentSettings()
    elif env_state == "test":
        return TestingSettings()
    elif env_state == "local":
        return LocalSettings()
    else:
        raise ValueError(
            f"Invalid ENV_STATE: '{env_state}'. "
            "Must be one of 'local', 'dev', 'test', or 'prod'."
        )


# Instantiate the global master settings instance for the entire application
settings = get_settings()
