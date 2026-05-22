# Standard libs
from functools import lru_cache

# Non-Standard libs
# ...

# Own Modules
from .passwords import PasswordSecurityManager
from .tokens import TokenSecurityManager


class Security:
    """
    Unified entry point for all authentication and security operations.
    Acts as a clean namespace container holding dedicated password
    and token management domains.
    """
    def __init__(self) -> None:
        self.passwords = PasswordSecurityManager()
        self.tokens = TokenSecurityManager


@lru_cache(maxsize=1)
def get_security() -> Security:
    """
    Single source of truth for security managers.
    Cached for performance to ensure only one instance exists.
    """
    return Security()


# Instantiate the global master instance for the application
security = get_security()
