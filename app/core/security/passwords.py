# === Standard libs ===
# ...

# === Non-Standard libs ===
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


class PasswordSecurityManager:
    """
    Handles stateful cryptographic operations for system passwords.
    Encapsulates the Argon2ID hashing pipeline configuration locally.
    """
    def __init__(self) -> None:
        self._argon2_hasher = Argon2Hasher(
            memory_cost=65536,
            time_cost=3,
            parallelism=4
        )
        self._password_hash = PasswordHash((self._argon2_hasher,))

    def hash(self, password: str) -> str:
        """Generates a secure, one-way cryptographic hash of a plain text password."""
        return self._password_hash.hash(password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain text password against its matching cryptographic hash."""
        return self._password_hash.verify(plain_password, hashed_password)