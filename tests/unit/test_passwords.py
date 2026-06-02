# Non-Standard libs
import pytest

# Own Modules
from core.security.passwords import PasswordSecurityManager
from core.settings import settings


def test_password_hashing_creates_secure_string():
    """
    Asserts that clear-text inputs generate secure, irreversible
    cryptographic strings bound to the Argon2id algorithmic prefix.
    """
    manager = PasswordSecurityManager()
    plain_password = "Senior_Architect_2026!$"

    hashed_password = manager.hash(plain_password)

    assert hashed_password != plain_password
    assert "$argon2id$" in hashed_password


def test_password_verification_success_and_failure():
    """
    Verifies that the validation manager correctly evaluates exact matches
    and successfully rejects invalid clear-text inputs against an active hash.
    """
    manager = PasswordSecurityManager()
    plain_password = "CorrectPassword123"
    wrong_password = "WrongPassword123"

    hashed_password = manager.hash(plain_password)

    # Assert successful match evaluation matrix
    assert manager.verify(plain_password, hashed_password) is True
    # Assert failed match verification conditions
    assert manager.verify(wrong_password, hashed_password) is False


def test_password_hashing_is_probabilistic_via_salting():
    """
    SCENARIO: A system must never generate identical hashes for identical passwords.
    WHY: If two users have the password "123456", their hashes in the DB must be different
    to prevent Rainbow Table attacks. Argon2id must inject a unique random salt every time.
    """
    manager = PasswordSecurityManager()
    password = "StaticPasswordToTestSalting123!"

    hash_one = manager.hash(password)
    hash_two = manager.hash(password)

    # Hashes must be completely unique due to the internal secure random salt
    assert hash_one != hash_two
    assert "$argon2id$" in hash_one
    assert "$argon2id$" in hash_two


def test_password_hashing_empty_string():
    """
    SCENARIO: Handling an empty string execution.
    WHY: Pydantic validation might catch this upstream, but the cryptographic core engine
    must be safe enough to handle empty values without crashing, generating a valid hash
    and verifying it properly.
    """
    manager = PasswordSecurityManager()
    empty_password = ""

    hashed = manager.hash(empty_password)

    assert len(hashed) > 0
    assert "$argon2id$" in hashed
    assert manager.verify(empty_password, hashed) is True
    assert manager.verify("some_other_password", hashed) is False


@pytest.mark.parametrize("extreme_password", [
    "A",  # Ultra-short boundary condition
    "a" * 100,  # Standard Pydantic maximum length anchor
    "★🎸🔥 Unicode Check ⚡⚠💠",  # Complex Multi-byte UTF-8 character arrays
    "Password\nWith\nNewlines\tAnd\tTabs",  # Control sequences and whitespaces
    "'; DROP TABLE users; --",  # SQL Injection payload pattern simulation
    "<script>alert('xss')</script>"  # Cross-Site Scripting input vector simulation
])
def test_password_management_with_extreme_and_exotic_inputs(extreme_password: str):
    """
    SCENARIO: Testing boundary conditions, multi-byte UTF-8 structures, and injection attacks.
    WHY: Malicious users can send complex strings to exploit buffer sizes or encoding bugs.
    Argon2id operates on bytes, so it must handle any valid UTF-8 string smoothly.
    """
    manager = PasswordSecurityManager()

    hashed = manager.hash(extreme_password)

    assert "$argon2id$" in hashed
    assert manager.verify(extreme_password, hashed) is True
    assert manager.verify(extreme_password + " ", hashed) is False


def test_password_hashing_huge_payload_handling():
    """
    SCENARIO: Over-sized text block execution (Denial of Service mitigation).
    WHY: Attackers might send a 10 Megabyte string to exhaust CPU cycles during hashing.
    We verify how the engine handles long strings (e.g., 5000 characters).
    """
    manager = PasswordSecurityManager()
    huge_password = "SuperLongPasswordVector" * 250  # 5750 characters total

    hashed = manager.hash(huge_password)

    assert "$argon2id$" in hashed
    assert manager.verify(huge_password, hashed) is True


def test_password_verification_with_malformed_hashes():
    """
    SCENARIO: Submitting malformed, truncated, or modified hash strings into verify().
    WHY: Attackers tampering with API tracking parameters or database errors could pass a corrupt string.
    The verification engine must return False instead of raising unhandled internal library exceptions.
    """
    manager = PasswordSecurityManager()
    password = "MyValidPassword123!"

    # 1. Truncated or incomplete hash format
    assert manager.verify(password, "$argon2id$v=19$m=2048,t=1,p=1$") is False

    # 2. Complete random garbage text payload
    assert manager.verify(password, "completely_random_garbage_string_not_a_hash") is False

    # 3. Altered algorithmic token identifier
    valid_hash = manager.hash(password)
    tampered_algorithm_hash = valid_hash.replace("$argon2id$", "$argon2i$")
    assert manager.verify(password, tampered_algorithm_hash) is False


def test_password_settings_module_boundaries():
    """
    SCENARIO: Verifying active configuration settings inside the unit loop execution.
    WHY: Guarantees that our optimization pattern functions as intended and that the unit suite
    is explicitly reading the lightweight parameters from `.env.test`.
    """
    assert settings.ENV_STATE == "test"
    assert settings.passwords.ARGON2_MEMORY_COST == 2048
    assert settings.passwords.ARGON2_TIME_COST == 1
    assert settings.passwords.ARGON2_PARALLELISM == 1
