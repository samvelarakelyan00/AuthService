# 🛡️ AuthService v2

Industrial, high-performance asynchronous Identity & Authentication microservice built with **FastAPI**, **PostgreSQL** (via `asyncpg`), and **Redis**. 

Architected using modern cloud-native design principles, this service guarantees enterprise-grade security hardening, non-blocking asynchronous hardware utilization, deterministic environment management, and a robust **Docs-as-Code** infrastructure.

---

## 📋 1. Overview

`AuthService` acts as a centralized authentication hub and authorization provider. It handles secure user lifecycle frames, cryptographically validates identities, issues dual-layered token configurations, and monitors distributed active sessions.

### Key Performance & Architectural Metrics
* **Stateless API, Stateful Session Boundaries**: Leverages cryptographically signed JSON Web Tokens (JWT) for instant, stateless client verification while enforcing strict, stateful token revocation lists via an in-memory Redis cluster.
* **Non-Blocking I/O Engineering**: Built natively on Python 3.14+ utilizing FastAPI's ASGI event loop. Heavy CPU-bound cryptographic operations (Argon2id hashing) are explicitly offloaded to detached system worker threads to maximize horizontal networking capacity.
* **Security Hardening Standard**: Features baked-in protection mechanisms against classic web-application vectors, including timing side-channel attacks, JWT algorithm confusion exploits, cross-site scripting (XSS), and cross-site request forgery (CSRF).

---

## 🧬 2. Domain Model

The service encapsulates authentication logic within three highly optimized domain models, mapped directly from relational persistence down to strict serialization contracts.

### Core Domain Entities
1. **User Identity (`models/users.py`)**  
   Represents a distinct registered system user. Features indexed, strict constraints on unique `email` strings and holds highly extended `hashed_password` arrays natively compiled for multi-byte Argon2id strings.
2. **Session / Refresh Token (`models/tokens.py`)**  
   Tracks physical persistent authentication devices across the system. It records unique transaction footprints (`jti`), explicit expiration frames (`expires_at`), and immutable security auditing metadata, specifically parsing client `user_agent` strings and full-range `ip_address` vectors (fully supporting modern IPv6 mappings up to 45 characters).
3. **Data Validation Contracts (`schemas/`)**  
   Pre-compiled Pydantic v2 namespaces acting as boundary enforcement points. They block malformed string arrays, guarantee structural email patterns via strict compilation metrics, filter hidden data parameters to prevent injection or profile parameter poisoning, and encapsulate strong, multi-character regular-expression password policies.

---

## 🏛️ 3. Architecture & Security Topography

The microservice layout is decoupled into a tiered, modular pipeline that maintains an unambiguous separation of concerns:

```text
        [ Client Application Traversal: Web / Mobile ]
                             |
                             | HTTP Request Pipeline
                             v
           +-----------------------------------+

           |        FastAPI ASGI Engine        |
           |-----------------------------------|
           |   • OpenAPI Contracts / Routing   |
           |   • Dependency Injection Context  |
           |   • Token / Session Extraction    |
           +-----------------------------------+

             |                               |
             | CPU-Bound Offloading          | Non-Blocking Connection Pool
             v                               v
   +--------------------+         +--------------------+

   |   Threadpool Workers|         |   Redis 7 Cluster  |
   |--------------------|         |--------------------|
   | • Argon2id Hashing |         | • Token Whitelist  |
   | • 15s Grace Period |         | • Active Tracking  |
   +--------------------+         +--------------------+
             |
             | Async Persistent Pool (AsyncPG)
             v
   +--------------------+

   | PostgreSQL 16 DBMS |
   |--------------------|
   | • Normal Users DB  |
   | • Historical Audit |
   +--------------------+
```

### Advanced Security Engineering Implementations
* **Timing Attack Eradication via Dummy Iterations**: To prevent malicious data enumeration via execution-latency variance, login attempts for non-existent users trigger a structural fake verification against an isolated cryptographic dummy hash. This ensures uniform API response timings across both existing and nonexistent profiles.
* **15-Second Concurrency Grace Period**: The Token Rotation engine (`/refresh`) wraps state mutations inside an atomic Redis multi-key pipeline transaction. When a token is rotated, the parent identity key transitions to a `"rotated"` status with an active 15-second survival window. This safely neutralizes front-end concurrency race conditions caused by overlapping client browser asset requests.
* **Hybrid Storage Vector Isolation**: Access tokens are kept short-lived (15 minutes or 1 minute in local development), designed for secure client-side in-memory application retention. Refresh tokens are isolated from JS engine interception entirely, injected via an opaque `HttpOnly`, `Secure` (activated via `prod` configurations), `SameSite=Lax` browser cookie context.

---

## 🚀 4. Getting Started

Follow these steps to deploy a fully configured local runtime instance containing isolated databases, caching clusters, and background schema structures.

### Prerequisites
* Docker and Docker Compose installed on your host system.
* A valid terminal runtime environment.

### Step-by-Step Initialization

#### 1. Instantiate the Environment Mapping File
Clone the repository and copy the explicit template environment tracking parameters into an active file:
```bash
cp .env.example .env
```
*Note: The local configuration system uses `.gitignore` bounds to guarantee that `.env`, `.env.test`, and `docker-compose.override.yml` files never leak into upstream source controls.*

#### 2. Execute the Automated Multi-Container Infrastructure Boot
Trigger the global multi-service build command:
```bash
docker compose up --build
```
**Orchestration Sequence Checklist:**
1. The PostgreSQL container initializes and activates its standard availability `healthcheck`.
2. The `migrations` container detects the verified database status (`pg_isready`), executes the full Alembic database schema upgrade suite down to the latest tracking point (`alembic upgrade head`), and terminates cleanly with exit-code `0`.
3. The main `fastapi-app` container fires up Uvicorn, establishes operational verification probes (`SELECT 1` on PostgreSQL and a ping payload to Redis), and exposes the network application boundary.

#### 3. Verify System Operations
Once the startup logs finalize, check the microservice endpoints:
* **Interactive OpenAPI/Swagger UI Portal**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Alternative ReDoc Architecture Portal**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **System Vital Probe (Health Check)**: Run a GET request to `http://localhost:8000/`

#### 4. Run the Automated Unit & Integrity Test Suite
Execute the testing framework using lightweight, optimized Argon2 parameters inside the virtual test layer:
```bash
docker compose run --rm fastapi-app sh -c "ENV_STATE=test uv run pytest"
```

---

## 📐 5. Code Conventions

The engineering team maintains code quality by adhering to strict runtime guidelines:
* **Strict Single Source of Truth Settings**: Configurations are unified via Pydantic `BaseSettings`. Direct manipulation of `os.getenv` inside sub-modules is forbidden. Settings initialization uses an active `@lru_cache(maxsize=1)` wrapper to ensure high-performance data delivery across imports.
* **Complete Async Engine Compliance**: Database calls are asynchronous using SQLAlchemy 2.0 `Mapped` schemas and `async_sessionmaker`. The parameter `expire_on_commit=False` is enforced to prevent implicit greenlet lazy-loading boundary breaks outside active database sessions.
* **Fail-Fast Structural Initialization**: If any dependent caching network or primary datastore fails its startup probe during the `lifespan` initialization frame, the application executes an immediate critical system stop (`raise error`), allowing modern container orchestrators (like Kubernetes) to trap and flag deployment anomalies immediately.
* **Isolated Trace Logs**: Standard imports use discrete logger lookups (`logging.getLogger(__name__)`). Sensitive parameter parameters (such as tokens or encryption strings) utilize Pydantic `SecretStr` configurations to prevent text leakage in output streams.

---

## 📦 6. Key Dependencies

The service uses a curated stack of modern libraries managed through Astral's highly optimized `uv` ecosystem:

* **`uv` (Dependency Manager)**: Manages dependencies via a deterministic lockfile mechanism using frozen synchronization arguments (`uv sync --frozen`).
* **`fastapi` & `uvicorn`**: Powers the underlying high-performance, asynchronous web routing layer.
* **`sqlalchemy` & `asyncpg`**: Provides advanced object-relational mapping alongside native, non-blocking PostgreSQL driver connectivity.
* **`pwdlib[argon2]`**: Implements secure password hashing compliant with modern OWASP cryptographic standards.
* **`pyjwt`**: Handles stateless signing and decoding of JWT vectors, enforcing explicit cryptographic signature controls.
* **`boto3`**: Provides native integration with cloud services, automatically pulling secrets from AWS SSM Parameter Store when running in production (`ENV_STATE=prod`).
* **`time-machine`**: Freezes and manipulates system clocks within test suites to test short token TTL expiration thresholds deterministically.

---

## 🛠️ 7. FAQ / Troubleshooting

### Q1: The `fastapi-app` container is stuck waiting or crashes on initialization?
* **Root Cause**: The orchestrator enforces strict sequence policies. The main application will not start unless the `migrations` container exits with an absolute success flag (`0`), which in turn requires the database health check (`pg_isready`) to pass.
* **Solution**: Inspect the database logs (`docker compose logs db`) to ensure your local volumes are not corrupted and that user credentials match your `.env` parameters.

### Q2: Why do tests run so fast despite using heavy Argon2id encryption?
* **Root Cause**: The testing layer applies a performance optimization trick. While production environments use intensive memory boundaries (`65536` bytes), `.env.test` lowers these parameters to a lightweight profile (`ARGON2_MEMORY_COST=2048`, `TIME_COST=1`, `PARALLELISM=1`).
* **Solution**: This is intended behavior. It ensures your CI/CD test pipeline runs in seconds while maintaining full cryptographic validation testing coverage.

### Q3: How do production servers handle configurations without an active `.env` file?
* **Root Cause**: In cloud production environments (`ENV_STATE=prod`), the application switches its provider settings class to `ProductionSettings`.
* **Solution**: It completely bypasses disk-based files, leveraging `SSMSettingsSource` to paginated-fetch and decrypt all runtime parameters directly from the AWS SSM Parameter Store hierarchy at path `/AuthService/prod/`.

---

## 📂 Repository Documentation Tree

For a deeper dive into the service architecture, navigate to the specific engineering files under the `/docs` folder:
1. **[01_architecture.md](/docs/01_architecture.md)**: Deep technical exploration of domain data designs, security context tracking, and timing threat mitigation models.
2. **[02_operations.md](/docs/02_operations.md)**: Comprehensive guide to connection pool metrics, variable specifications, and automated cloud deployments via AWS CLI.
3. **[03_api_contracts.md](/docs/03_api_contracts.md)**: In-depth documentation of frontend integration rules, API structures, cookie mechanics, and JSON schemas.
4. **[04_testing_suite.md](/docs/04_testing_suite.md)**: Detailed mapping of automated test matrices, boundary attacks protection, and conftest patching hacks.

---
