# 🧪 Automated Test Suite & Security Boundary Verification

This document defines the automated quality assurance matrix, cryptographic boundary tests, and testing configuration overrides for **AuthService v2**. It serves as the single source of truth for QA automation engineers and core backend developers maintaining the test suite.

---

## 1. Local Test Execution Frame

The test suite runs inside a dedicated testing environment state using explicit performance switches to guarantee optimal execution times. 

To execute the unit testing block locally outside or inside container environments, use the following command:

```bash
PYTHONPATH=app ENV_STATE=test uv run pytest tests/unit/ -v -p no:warnings
```

### Command Flags Breakdown
*   **`PYTHONPATH=app`**: Forces the Python runtime interpreter to append the core application workspace module directory directly to the resolution lookup path, preventing import mismatch faults.
*   **`ENV_STATE=test`**: Instructs the Pydantic configurations factory engine to load the explicit `.env.test` file layer instead of standard local variable assets.
*   **`-v`**: Activates verbose logging output displaying the precise execution success matrices of individual test cases.
*   **`-p no:warnings`**: Suppresses non-critical library warnings from cluttering stdout streams during high-speed CI execution.

---

## 2. CI/CD Cryptographic Performance Optimization Hack

**The Infrastructure Threat**: The **Argon2id** password-hashing algorithm is intentionally designed to be computationally slow and resource-heavy to defeat hardware brute-force attacks. In production environments, it consumes massive amounts of RAM and CPU cycles per calculation (~150ms execution overhead). Running hundreds of user lifecycle integration tests using these production parameters would completely stall CI/CD pipelines, driving up compute costs and slowing down deployment times.

**The Solution (`.env.test`)**:
The testing environment applies an isolated hardware-cost down-scaling override strategy. When `ENV_STATE=test` is evaluated, the system injects highly lowered cryptographic cost parameters directly into the `PasswordSettings` validation namespace:

```ini
# .env.test Cryptographic Degradation Constants
ARGON2_MEMORY_COST=2048   # Reduced from 65,536 bytes
ARGON2_TIME_COST=1        # Reduced from 3 iterations
ARGON2_PARALLELISM=1     # Reduced from 4 active threads
```

### Production vs. Test Comparison Matrix
*   **Production State**: High memory cost requirements (`65,536`) prevent GPU/ASIC cluster acceleration cracking attempts.
*   **Testing State**: Lowered memory cost requirements (`2,048`) force Argon2id calculations to execute in sub-millisecond windows. 
*   **Architectural Guarantee**: This optimization ensures that test runs pass in seconds while maintaining full validation coverage over the underlying hashing, salting, and verification algorithms.

---

## 3. Deterministic Time Manipulation & Clock Skew Verification

**The Threat**: Testing JSON Web Token (JWT) lifetimes (`exp` claims) is notoriously prone to flaky tests ("flaky tests"). Relying on native system timers like `time.sleep(60)` to wait for an access token to expire adds artificial delays to testing pipelines and creates race conditions based on underlying host CPU scheduling variances.

**The Implementation (`tests/unit/test_tokens.py`)**:
The testing environment uses the specialized `time-machine` library to mock and control the system clock deterministically during test execution:

```python
# Freeze the system clock precisely at a reference UTC anchor point
with time_machine.travel("2026-06-02 12:00:00 +0000") as traveller:
    access_meta = TokenSecurityManager.create_access_token(user_id="888")

    # Shift system time forward to 1 second before absolute token expiration
    traveller.shift(59)
    assert TokenSecurityManager.verify_token(access_meta["token"], expected_type="access") is not None

    # Advance exactly 1 more second to cross the expiration boundary
    traveller.shift(1)
    with pytest.raises(ValueError, match="Token signature validation breached: Token expired"):
        TokenSecurityManager.verify_token(access_meta["token"], expected_type="access")
```
This approach guarantees that token lifecycle checks pass with single-second precision across all local environments and remote cloud deployment runtimes.

---

## 4. Security Hardening Exploits Testing Matrix

The automated testing layer acts as a security gateway, maintaining strict regression tests against known cryptographic exploit vectors.

### 4.1. None Algorithm Exploit Protection Test
Checks against token spoofing vulnerabilities where malicious actors modify headers to `{"alg": "none"}` and strip the signature block to bypass security filters.
*   **The Test (`test_verify_token_none_algorithm_exploit_mitigation`)**: Generates an unsigned token utilizing the insecure `none` algorithm string. The core verification module must successfully intercept the payload and raise an explicit signature processing integrity error.

### 4.2. Algorithm Confusion Attack Protection Test
Prevents asymmetric/symmetric key substitution vulnerabilities where an attacker signs a forged token using a public key as a symmetric HMAC-HS256 secret.
*   **The Test (`test_verify_token_algorithm_confusion_attack`)**: Signs a token payload using an unauthorized alternate signature algorithm identifier (`HS512` instead of the configured `HS256`). The validation engine flags the anomaly and rejects the token.

### 4.3. Extra Parameters Filtering Validation Test
Ensures that data boundaries are strictly enforced and prevents parameter injection or profile poisoning.
*   **The Test (`test_user_out_schema_ignores_extra_fields`)**: Injects unauthorized fields (e.g., `"password_hash": "leak_payload"` and `"role": "hacker"`) into the validation model layer. The schema must cleanly strip the extra properties, ensuring that sensitive data parameters never bleed out to client responses.

---

## 5. Runtime Monkeypatching Hack (`tests/conftest.py`)

**The Issue**: The `PyJWT` library generates an `InsecureKeyLengthWarning` exception whenever short secret strings are parsed within local testing parameters (as seen in `.env.test`). While we can suppress this warning using standard Pytest settings, the warning class itself dynamically drifts between different internal workspaces (`jwt.exceptions` vs. `jwt.warnings`) depending on the sub-version of the installed package. This discrepancy frequently causes automated test suites to crash with an unhandled `AttributeError` during initialization.

**The Fix Implementation**:
The test runner applies a dynamic monkeypatch within `conftest.py` upon initial boot to standardize the workspace modules map:

```python
import sys
import jwt

# Force Pytest to find the warning class where it is looking for it
if not hasattr(jwt.exceptions, "InsecureKeyLengthWarning"):
    import jwt.warnings
    sys.modules["jwt.exceptions"].InsecureKeyLengthWarning = getattr(
        jwt.warnings, "InsecureKeyLengthWarning", UserWarning
    )
```
This ensures absolute stability across deployment pipelines regardless of the exact micro-versions of underlying third-party dependencies.

---
*AuthService v2 Testing Suite Manual • End of Technical Documentation Ecosystem*