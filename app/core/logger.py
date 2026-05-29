"""
Core System Logging Architecture Engine.

Provides unified stream routing, file-rotation abstractions, and automated JSON
serialization switches to guarantee an effortless future migration to an ELK Stack.
"""

# Standard libs
import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

# Own Modules
from core.settings import settings


class AppLoggingConfigurator:
    """
    Enterprise Configuration Factory for application telemetry and logs.

    Dynamically constructs Python Logging Dictionary Schemas based on the
    validated operational environment state.
    """

    def __init__(self) -> None:
        self.log_level: str = settings.logging.LOG_LEVEL
        self.log_dir: Path = Path(settings.logging.LOG_DIR)
        self.is_json: bool = settings.logging.LOG_JSON_FORMAT
        self.max_bytes: int = settings.logging.LOG_MAX_BYTES
        self.backup_count: int = settings.logging.LOG_BACKUP_COUNT

        # Definitive structured text formats for human validation
        self.CONSOLE_FORMAT: str = (
            "%(asctime)s [%(levelname)s] %(name)s "
            "(%(filename)s:%(lineno)d) - %(message)s"
        )
        self.FILE_FORMAT: str = (
            "%(asctime)s [%(levelname)s] %(name)s "
            "[Process ID: %(process)d | Thread: %(threadName)s] "
            "(%(filename)s:%(lineno)d) - %(message)s"
        )

    def _build_formatter_configurations(self) -> Dict[str, Any]:
        """Generates target formatting dictionaries depending on operational topology."""
        if self.is_json:
            return {
                "elk_json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s %(filename)s "
                        "%(lineno)d %(message)s %(process)d %(threadName)s"
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%SZ",
                }
            }

        return {
            "console_human": {"format": self.CONSOLE_FORMAT, "datefmt": "%Y-%m-%d %H:%M:%S"},
            "file_human": {"format": self.FILE_FORMAT, "datefmt": "%Y-%m-%d %H:%M:%S"},
        }

    def generate_dict_config(self) -> Dict[str, Any]:
        """
        Assembles structural standard dictionary payload mapping out system targets.

        Preserves third-party log signatures (Uvicorn, Alembic) while aligning
        them to custom enterprise specifications.
        """
        formatters = self._build_formatter_configurations()
        active_formatter = "elk_json" if self.is_json else "file_human"
        console_formatter = "elk_json" if self.is_json else "console_human"

        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.log_level,
                    "formatter": console_formatter,
                    "stream": sys.stdout,
                },
                "app_rotating_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.log_level,
                    "formatter": active_formatter,
                    "filename": str(self.log_dir / "app.log"),
                    "maxBytes": self.max_bytes,
                    "backupCount": self.backup_count,
                    "encoding": "utf-8",
                },
                "error_rotating_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "ERROR",
                    "formatter": active_formatter,
                    "filename": str(self.log_dir / "errors.log"),
                    "maxBytes": self.max_bytes,
                    "backupCount": self.backup_count,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "": {  # Root Logger interception matrix
                    "handlers": ["console", "app_rotating_file", "error_rotating_file"],
                    "level": self.log_level,
                },
                "uvicorn": {
                    "handlers": ["console", "app_rotating_file", "error_rotating_file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console", "app_rotating_file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "alembic": {
                    "handlers": ["console", "app_rotating_file"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }


def initialize_system_logging() -> None:
    """
    Idempotent bootstrap orchestrator hook.
    Executes structural logging runtime bindings immediately upon microservice setup.
    """
    configurator = AppLoggingConfigurator()
    logging.config.dictConfig(configurator.generate_dict_config())
