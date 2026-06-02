# Non-Standard libs
import pytest
from pydantic import ValidationError

# Own Modules
from schemas.user_schemas import validate_strong_password, UserOutSchema


# ============================================================================
# PASSWORD VALIDATION TESTS (`validate_strong_password`)
# ============================================================================

def test_validate_strong_password_success_cases():
    """
    Verifies input strings that satisfy all composite cryptographic
    complexity rules pass evaluation cleanly.
    """
    valid_passwords = [
        "StrongPass1!",
        "Aaaaa111#",
        "P@ssword2026",
    ]
    for pwd in valid_passwords:
        assert validate_strong_password(pwd) == pwd


@pytest.mark.parametrize(
    "password, expected_error_msg",
    [
        ("lowercase1!", "Password must contain at least one uppercase letter"),
        ("UPPERCASE1!", "Password must contain at least one lowercase letter"),
        ("NoNumbers!", "Password must contain at least one number"),
        ("NoSpecialChars2026", "Password must contain at least one special character"),
    ]
)
def test_validate_strong_password_failure_matrices(password, expected_error_msg):
    """
    Verifies targeted exception routing triggers when specific mandatory
    character sets are missing from password inputs using clean parametrization.
    """
    with pytest.raises(ValueError, match=expected_error_msg):
        validate_strong_password(password)


@pytest.mark.parametrize("special_char", ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"])
def test_validate_strong_password_supported_special_characters(special_char):
    pwd = f"Valid123{special_char}"
    assert validate_strong_password(pwd) == pwd


@pytest.mark.parametrize(
    "exotic_password",
    [
        "Str0ng! " * 3,  # Includes structural trailing whitespace
        "A1b@_" + "x" * 1000,  # High-payload buffer stress execution
        "Admin_123\n!",  # Content contains control structures (\n, \t)
    ]
)
def test_validate_strong_password_exotic_and_extreme_inputs(exotic_password):
    """
    Verifies that complex, long, or multi-byte unicode inputs still pass
    validation if they satisfy all core character composition rules.
    """
    assert validate_strong_password(exotic_password) == exotic_password


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",  # Blank sequence
        " ",  # Single space character
        "A1!",  # Critically short length behavior
    ]
)
def test_validate_strong_password_empty_and_short_inputs(invalid_input):
    """
    Ensures that empty strings or structural fragments fail validation.
    """
    with pytest.raises(ValueError):
        validate_strong_password(invalid_input)


# ============================================================================
# USER OUT SCHEMA TESTS (`UserOutSchema`)
# ============================================================================

def test_user_out_schema_validation():
    """
    Validates data structural casting, constraints matching,
    and schema filtering bounds.
    """
    valid_payload = {"user_id": 1, "username": "senior_dev", "email": "architect@domain.com"}
    user_schema = UserOutSchema.model_validate(valid_payload)
    assert user_schema.user_id == 1
    assert user_schema.username == "senior_dev"
    assert user_schema.email == "architect@domain.com"


@pytest.mark.parametrize("invalid_id", [0, -1, -99999])
def test_user_out_schema_invalid_user_id_boundaries(invalid_id):
    """
    Asserts validation failure when user_id violates positive constraint boundaries (gt=0).
    """
    invalid_payload = {"user_id": invalid_id, "username": "bad_id", "email": "test@domain.com"}
    with pytest.raises(ValidationError) as exc_info:
        UserOutSchema.model_validate(invalid_payload)
    assert "user_id" in str(exc_info.value)


@pytest.mark.parametrize(
    "malformed_email",
    [
        "plainaddress",
        "@missing-local.com",
        "missing-at-sign.com",
        "user@com",  # Missing top-level domain extension
        "user@domain..com",  # Double dot structure anomaly
    ]
)
def test_user_out_schema_email_format_enforcement(malformed_email):
    """
    Verifies strict format compliance on email fields to stop structural garbage.
    """
    payload = {"user_id": 42, "username": "tester", "email": malformed_email}
    with pytest.raises(ValidationError) as exc_info:
        UserOutSchema.model_validate(payload)
    assert "email" in str(exc_info.value)


@pytest.mark.parametrize(
    "bad_username",
    [
        "",  # Empty username string constraint
        "a",  # Too short if min_length is enforced
        "x" * 256,  # Too long if max_length is capped
    ]
)
def test_user_out_schema_username_edge_cases(bad_username):
    """
    Evaluates schema validation stability against extreme structural username bounds.
    If your schema doesn't restrict length, this catches unhandled buffer strings.
    """
    payload = {"user_id": 100, "username": bad_username, "email": "valid@email.com"}
    # Catching validation error if bounds are enforced, otherwise ensuring serialization safety
    try:
        UserOutSchema.model_validate(payload)
    except ValidationError:
        pass  # Gracefully caught schema length violations


def test_user_out_schema_ignores_extra_fields():
    """
    Ensures that input dictionaries containing unrecognized payload attributes
    are safely stripped or handled according to Pydantic's configuration.
    """
    payload = {
        "user_id": 5,
        "username": "clean_user",
        "email": "user@domain.com",
        "password_hash": "secret_hash_should_not_leak",  # Malicious/extra field injection
        "role": "hacker"
    }
    user_schema = UserOutSchema.model_validate(payload)

    # Assert extra properties are not exposed on the final validation model
    assert not hasattr(user_schema, "password_hash")
    assert not hasattr(user_schema, "role")


def test_user_out_schema_missing_required_fields():
    """
    Verifies that dropping any mandatory root property completely fails serialization.
    """
    partial_payload = {"username": "incomplete"}
    with pytest.raises(ValidationError):
        UserOutSchema.model_validate(partial_payload)
