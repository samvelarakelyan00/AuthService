# Standard libs
from pathlib import Path
from typing import Literal

# Non-Standard libs
# Pydantic
from pydantic import BaseModel, Field, field_validator


class LoggingSettings(BaseModel):
    """
    Data validation schema for system-wide log engines.
    Guarantees directories exist and variables follow strict DevOps structures.
    """
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    # Toggles between human-readable console output (Local) and JSON serialization (Prod/ELK)
    LOG_JSON_FORMAT: bool = Field(default=False)

    # Resolves directly to the repository root directory outside the application module
    LOG_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent.parent.parent / "logs"
    )

    # 10MB default file limits before rotating
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024 * 1024)
    LOG_BACKUP_COUNT: int = Field(default=5, ge=1)

    @field_validator("LOG_DIR", mode="before")
    @classmethod
    def ensure_log_dir_exists(cls, v: Path) -> Path:
        """
        Idempotent infrastructure guard. Pre-creates the system
        logging filesystem partition before the runtime attaches handlers.
        """
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path
