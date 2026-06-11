# Standard libs
from pathlib import Path
from typing import Literal, Any

# Non-Standard libs
from pydantic import BaseModel, Field, field_validator


class LoggingSettings(BaseModel):
    """
    Data validation schema for system-wide log engines.
    Guarantees directories exist and variables follow strict DevOps structures.
    """
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    LOG_JSON_FORMAT: bool = Field(default=False)

    # Resolves directly to the repository root directory outside the application module
    LOG_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent.parent.parent / "logs"
    )

    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024 * 1024)
    LOG_BACKUP_COUNT: int = Field(default=5, ge=1)

    @field_validator("LOG_DIR", mode="before")
    @classmethod
    def ensure_log_dir_exists(cls, v: Any) -> Path:
        """
        Idempotent infrastructure guard. Resolves absolute target routing
        and ensures partitions exist before runtime handles bind.
        """
        # If it's a relative path name or string, compute it relative to the true repository root
        path = Path(v)
        if not path.is_absolute():
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            path = repo_root / path

        path.mkdir(parents=True, exist_ok=True)
        return path
