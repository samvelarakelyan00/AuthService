# === Standard libs ===
# ...

# === Non-Standard libs ===
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# === Own Modules ===
from core.settings import settings


class PasswordSecurityManager:
    """
    Handles stateful cryptographic operations for system passwords.
    Encapsulates the Argon2ID hashing pipeline configuration locally.
    """
    def __init__(self) -> None:
        self._argon2_hasher = Argon2Hasher(
            memory_cost=settings.passwords.ARGON2_MEMORY_COST,
            time_cost=settings.passwords.ARGON2_TIME_COST,
            parallelism=settings.passwords.ARGON2_PARALLELISM
        )
        self._password_hash = PasswordHash((self._argon2_hasher,))

    def hash(self, password: str) -> str:
        """Generates a secure, one-way cryptographic hash of a plain text password."""
        return self._password_hash.hash(password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain text password against its matching cryptographic hash."""
        return self._password_hash.verify(plain_password, hashed_password)