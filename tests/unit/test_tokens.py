# Standard libs
import datetime

# Non-Standard libs
import time_machine
import pytest
import jwt

# Own Modules
from core.security.tokens import TokenSecurityManager
from core.settings import settings


def test_create_access_and_refresh_tokens_structures():
    """
    Validates payload layouts, internal tracking variables (jti),
    and TTL calculation packages for generated tokens.
    """
    user_id = "1337"

    access_data = TokenSecurityManager.create_access_token(user_id=user_id)
    refresh_data = TokenSecurityManager.create_refresh_token(user_id=user_id)

    # Assert structural packaging envelopes
    assert "token" in access_data and "jti" in access_data and "ttl_seconds" in access_data
    assert "token" in refresh_data and "jti" in refresh_data and "ttl_seconds" in refresh_data

    # Decode and verify exact internal claims
    payload_access = TokenSecurityManager.verify_token(access_data["token"], expected_type="access")
    payload_refresh = TokenSecurityManager.verify_token(refresh_data["token"], expected_type="refresh")

    assert payload_access["sub"] == user_id
    assert payload_refresh["sub"] == user_id


def test_verify_token_type_mismatch_raises_value_error():
    """
    Guarantees token decoding aborts immediately if token types
    do not match validation expectations.
    """
    user_id = "555"
    access_data = TokenSecurityManager.create_access_token(user_id=user_id)

    # Submitting an access token to a gateway expecting a refresh type must fail
    with pytest.raises(ValueError, match="Invalid token type mapping context"):
        TokenSecurityManager.verify_token(access_data["token"], expected_type="refresh")


def test_verify_token_expired_signature_detection():
    """
    Validates that the token decoder accurately intercepts expired
    signatures when evaluated outside token lifespan boundaries.
    """
    user_id = "777"

    # Freeze the clock deterministically at a reference anchor point
    with time_machine.travel("2026-06-02 12:00:00 +0000") as traveller:
        access_data = TokenSecurityManager.create_access_token(user_id=user_id)

        # Token is immediately operational and valid
        assert TokenSecurityManager.verify_token(access_data["token"], expected_type="access")

        # Shift system time forward by 2 minutes (access expiry threshold is 1 minute in .env.test)
        traveller.shift(60 * 2)

        with pytest.raises(ValueError, match="Token signature validation breached: Token expired"):
            TokenSecurityManager.verify_token(access_data["token"], expected_type="access")


def test_verify_token_tampered_signature_detection():
    """
    Guarantees verification processing fails if external actors modify
    or corrupt characters within the cryptographic signature string.
    """
    user_id = "999"
    access_data = TokenSecurityManager.create_access_token(user_id=user_id)
    corrupted_token = access_data["token"] + "xyz"

    with pytest.raises(ValueError, match="Token validation breach: Signature processing integrity error"):
        TokenSecurityManager.verify_token(corrupted_token, expected_type="access")


def test_verify_token_none_algorithm_exploit_mitigation():
    """
    SECURITY SCENARIO: Vulnerability protection against "None" Algorithm Exploits.
    WHY: Legacy or poorly configured JWT decoders can be tricked if an attacker modifies the token
    header to {"alg": "none"} and strips the signature, letting them forge tokens.
    Our system uses an explicit algorithms constraint check to block this vector.
    """
    payload = {
        "exp": 9999999999,
        "iat": 1111111111,
        "sub": "compromised_user_id",
        "token_type": "access",
        "jti": "fake-jti-uuid"
    }
    # Manually generate an unsigned token using the insecure "none" algorithm
    unsecured_forged_token = jwt.encode(payload=payload, key="", algorithm="none")

    with pytest.raises(ValueError, match="Token validation breach: Signature processing integrity error"):
        TokenSecurityManager.verify_token(unsecured_forged_token, expected_type="access")


@pytest.mark.filterwarnings("ignore:The HMAC key is:jwt.exceptions.InsecureKeyLengthWarning")
def test_verify_token_algorithm_confusion_attack():
    """
    SECURITY SCENARIO: Vulnerability protection against Algorithm Confusion/Substitution attacks.
    WHY: If a system expects an asymmetric public/private key algorithm (like RS256) but an attacker
    signs a forged token using the public key as a symmetric HMAC-HS256 secret key, a loose decoder
    might validate it. We force an exact algorithm match from settings to prevent this exploit.
    """
    user_id = "attacker_id"
    payload = {"sub": user_id, "token_type": "access", "jti": "attack-jti"}

    # Try signing with an alternate algorithm (HS512 instead of your configured HS256)
    forged_algorithm_token = jwt.encode(
        payload=payload,
        key=settings.tokens.SECRET_KEY.get_secret_value(),
        algorithm="HS512"
    )

    with pytest.raises(ValueError, match="Token validation breach: Signature processing integrity error"):
        TokenSecurityManager.verify_token(forged_algorithm_token, expected_type="access")


@pytest.mark.parametrize("malformed_token_string", [
    "",  # Empty input check
    "not_even_a_jwt_format",  # Simple string without period delimiters
    "header.payload",  # Missing the mandatory third signature block segment
    "header.payload.signature.extra"  # Over-segmented string arrays
])
def test_verify_token_handling_of_structural_garbage_inputs(malformed_token_string: str):
    """
    SCENARIO: Submitting completely unparseable string variants to verify_token().
    WHY: Incoming client headers might contain corrupt data, truncated strings, or malformed payloads.
    The subsystem must catch these anomalies gracefully and throw the unified ValueError.
    """
    with pytest.raises(ValueError, match="Token validation breach: Signature processing integrity error"):
        TokenSecurityManager.verify_token(malformed_token_string, expected_type="access")


def test_verify_token_missing_expected_claims_handling():
    """
    SCENARIO: Token payload is syntactically valid but lacks mandatory system claims.
    WHY: An attacker could generate a valid JWT with an unrelated tool that is missing
    crucial fields like `token_type` or `jti`. The system must flag this missing context.
    """
    # Create a token missing the mandatory token_type variable entirely
    future_timestamp = int((datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).timestamp())
    incomplete_payload = {
        "sub": "user_123",
        "exp": future_timestamp  # Patched: Clean valid integer timestamp
    }
    raw_token = jwt.encode(
        payload=incomplete_payload,
        key=settings.tokens.SECRET_KEY.get_secret_value(),
        algorithm=settings.tokens.ALGORITHM
    )

    with pytest.raises(ValueError, match="Invalid token type mapping context"):
        TokenSecurityManager.verify_token(raw_token, expected_type="access")


def test_verify_token_precise_boundary_clock_skew():
    """
    SCENARIO: Edge-case precision validation at the exact second of expiration.
    WHY: Validates that token validity is evaluated precisely without safe-buffer drift.
    """
    user_id = "888"
    access_expiry_seconds = settings.tokens.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 60 seconds

    with time_machine.travel("2026-06-02 12:00:00 +0000") as traveller:
        access_meta = TokenSecurityManager.create_access_token(user_id=user_id)

        # Advance clock to exactly 59 seconds after creation (1 second before absolute expiration)
        traveller.shift(access_expiry_seconds - 1)
        assert TokenSecurityManager.verify_token(access_meta["token"], expected_type="access") is not None

        # Advance exactly 1 more second (the absolute threshold expiration mark)
        traveller.shift(1)
        with pytest.raises(ValueError, match="Token signature validation breached: Token expired"):
            TokenSecurityManager.verify_token(access_meta["token"], expected_type="access")


def test_access_token_strict_expiration_lifecycle():
    """
    SCENARIO: Verify the exact expiration lifecycle of a short-lived Access Token.
    WHY: Access tokens must burn out precisely after the configured duration
    (e.g., 1 minute in .env.test) to minimize the attack window if compromised.
    """
    user_id = "user_access_lifecycle"
    # Read the precise token lifetime in seconds directly from current config mapping
    expiry_seconds = settings.tokens.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    with time_machine.travel("2026-06-02 12:00:00 +0000") as traveller:
        # Create token at 12:00:00
        access_meta = TokenSecurityManager.create_access_token(user_id=user_id)

        # 1. Assert precise validation exactly 1 second before expiration (12:00:59)
        traveller.shift(expiry_seconds - 1)
        assert TokenSecurityManager.verify_token(access_meta["token"], expected_type="access") is not None

        # 2. Assert strict rejection exactly at the expiration second mark (12:01:00)
        traveller.shift(1)
        with pytest.raises(ValueError, match="Token signature validation breached: Token expired"):
            TokenSecurityManager.verify_token(access_meta["token"], expected_type="access")


def test_refresh_token_long_term_validity_and_expiration_lifecycle():
    """
    SCENARIO: Verify the long-term expiration lifecycle of a long-lived Refresh Token.
    WHY: Refresh tokens are designed for long-term sessions (e.g., 30 days / 43,200 minutes).
    We must ensure they remain valid across weeks and expire exactly at their final lifetime boundary.
    """
    user_id = "user_refresh_lifecycle"
    # Read the long-lived duration in minutes from configuration (43200 minutes = 30 days)
    expiry_minutes = settings.tokens.REFRESH_TOKEN_EXPIRE_MINUTES

    with time_machine.travel("2026-06-02 12:00:00 +0000") as traveller:
        # Create refresh token at Day 0
        refresh_meta = TokenSecurityManager.create_refresh_token(user_id=user_id)

        # 1. Assert metadata TTL matching configurations perfectly
        assert refresh_meta["ttl_seconds"] == expiry_minutes * 60

        # 2. Move time forward by 15 days (midway point of session validity)
        traveller.shift(60 * 60 * 24 * 15)
        # Token must pass validation seamlessly as the session is mid-lifecycle
        assert TokenSecurityManager.verify_token(refresh_meta["token"], expected_type="refresh") is not None

        # 3. Move time forward to 1 minute before absolute expiration (Day 30 minus 1 minute)
        # Total remaining shift to reach (30 days - 1 minute) from current Day 15 position
        remaining_valid_minutes = (expiry_minutes) - (60 * 24 * 15)
        traveller.shift(60 * (remaining_valid_minutes - 1))
        assert TokenSecurityManager.verify_token(refresh_meta["token"], expected_type="refresh") is not None

        # 4. Step forward exactly 60 seconds to breach the absolute 30-day session threshold
        traveller.shift(60)
        with pytest.raises(ValueError, match="Token signature validation breached: Token expired"):
            TokenSecurityManager.verify_token(refresh_meta["token"], expected_type="refresh")
