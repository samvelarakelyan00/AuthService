# Standard libs
# ...

# Own Modules
from core.security import (
    Security,
    get_security as _get_security,
)


def get_security() -> Security:
    """
    Dependency injection wrapper for FastAPI.
    Re‑exports the cached Security instance from core.security.
    """
    return _get_security()
