# ⚙️ DevOps Operations & Environment Matrix Specifications

This document defines the physical deployment configurations, database connection pool tuning parameters, environment matrix architectures, and automated deployment sequences for **AuthService v2**. It serves as the single source of truth for DevOps engineers, SREs, and platform administrators.

---

## 1. Global Environment Configuration Matrix

The application's runtime behavior transitions based on the value of the `ENV_STATE` environment variable. Pydantic dynamically selects and instantiates corresponding configuration modules via an advanced factory pattern wrapped inside a cached decorator frame.

| Infrastructure Domain | `local` (Development) | `test` (Automated Pytest / CI) | `dev` (Cloud Staging) | `prod` (Production Cluster) |
| :--- | :--- | :--- | :--- | :--- |
| **Configuration Source** | Real disk `.env` root file | Real disk `.env.test` file | Real disk `.env.dev` file | **AWS SSM Parameter Store** |
| **`DEBUG` Flag** | `True` | `True` | `True` / `False` | `False` |
| **Uvicorn Auto-Reload** | Enabled | Disabled | Disabled | Disabled |
| **Argon2id CPU Costs** | Heavy (`m=65536, t=3, p=4`) | Light (`m=2048, t=1, p=1`) | Heavy (`m=65536, t=3, p=4`) | Industrial Hardened Bounds |
| **SQL Engine Log Echo** | `True` (Raw stdout dump) | `False` | `False` | `False` |
| **Logger Output Engine** | Human-readable text streams | Suppressed / standard text | JSON payload vectors | **Structured JSON payloads** |
| **AWS Systems Manager** | Completely Bypassed | Completely Bypassed | Optional Cloud Integration | **Mandatory API Sourcing** |

---

## 2. Infrastructure Engineering & Connection Pool Tuning

To guarantee high scalability under load, connection boundaries for both relational storage and in-memory caches are explicitly throttled and managed via pooled network resources.

### 2.1. PostgreSQL Connection Resource Layout (`db/session.py`)
Managed through an asynchronous engine factory utilizing the `asyncpg` network communication driver.

*   **`POOL_SIZE` (Default: `5`)**: Defines the base baseline of persistent database connections held open by each application worker thread. Prevents TCP socket setup penalties during high-speed traffic flows.
*   **`MAX_OVERFLOW` (Default: `10`)**: Sets the maximum threshold of extra connections allowed to burst temporarily above the `POOL_SIZE` during severe traffic peaks.
*   **`POOL_TIMEOUT` (Default: `30`)**: The maximum number of seconds a concurrent thread will halt to acquire an available socket from the connection pool before raising an operational database failure exception.
*   **`POOL_RECYCLE` (Default: `3600`)**: Forces connections to gracefully close and re-allocate after exactly 1 hour of operational runtime. This eliminates stale connections and mitigates resource creep on database nodes.
*   **`POOL_PRE_PING` (Default: `True`)**: Activates automated heartbeats before passing a socket back to the router context. If an underlying network drop occurs, the engine cleans the pool stale socket and provisions a functional link transparently.

### 2.2. Redis Shared Resource Limits (`db/redis_connection.py`)
Utilizes a persistent connection manager initialized via `redis.asyncio` with string parsing configuration keys.

*   **`decode_responses=True`**: Forces raw Redis binary data structures to undergo automatic UTF-8 string typecasting on the fly at driver layer levels, removing manual processing strings from application controllers.
*   **`MAX_CONNECTIONS` (Default: `50`)**: Hard boundary limit assigned to `aioredis.ConnectionPool`. This restricts open file descriptors on Redis instances as the container architecture scales out horizontally across multiple availability zones.

---

## 3. Remote Secret Sourcing: AWS SSM Parameter Store

When `ENV_STATE=prod` is evaluated on boot, the application bypasses real disk files entirely by calling the specialized Pydantic provider resource layer `SSMSettingsSource`.

```text
  [ Container Boot Stage ] ---> Evaluates ENV_STATE == "prod"
                                      |
                                      v
                 [ SSMSettingsSource Class Initialization ]
                                      |
       +------------------------------+------------------------------+

       |                                                             |
       v                                                             v
 [ Fetch Region Environment ]                                [ Paginated SSM Call ]
 os.getenv("AWS_REGION", "us-east-1")                         Prefix Path: "/AuthService/prod/"
                                                             WithDecryption: True
                                                                     |
                                                                     v
                                                   [ Paginated Extraction Loop ]
                                                    Iterates through large parameter matrices
                                                    Strips prefix hierarchies automatically
                                                                     |
                                                                     v
                                                   [ Dynamic Settings Composition ]
                                                    Maps parameter strings directly into 
                                                    strongly-typed fields via Pydantic v2
```

### Resiliency & Fail-Safe Patterns
1.  **Automated Remote Pagination**: Leverages the official AWS paginator utility layer `get_parameters_by_path`. This prevents memory cut-offs and guarantees full extraction across multiple setting pages without reaching single-call threshold limits.
2.  **Runtime Decryption Handling**: The API specifically injects the flag `WithDecryption=True`, triggering automatic server-side AWS KMS decryption for target `SecureString` variables (e.g., database user secrets and JWT keys).
3.  **Fail-Fast Error Trapping**: Cloud network communication drops or IAM role mapping faults are safely caught within a try-except layer (`print(f"AWS SSM Error: {e}")`). This outputs structured telemetry data while forcing a systematic application halt due to invalid environment configurations.

---

## 4. Automation Deploy Orchestration Script (`/scripts/deploy.sh`)

Production application lifecycle rollouts are automated via a secure, idempotent shell deployment harness script. It acts as a safety gate for schema migration states.

```bash
#!/bin/bash

echo "--- Fetching parameters from AWS ---"
# Uses get-parameters-by-path with decryption filters. Parses trailing slashes,
# cleans tabs, converts properties into system variable exports on the fly.
export \$(aws ssm get-parameters-by-path \
    --path "/" \
    --recursive \
    --with-decryption \
    --region us-east-1 \
    --query "Parameters[*].[Name,Value]" \
    --output text | awk -F'/' '{print \$NF}' | sed 's/\t/=/')

echo "--- Building images ---"
docker compose build

echo "--- Running Migrations ---"
# Launches the alembic tracking container exclusively in the foreground
docker compose up migrations --exit-code-from migrations

# Pipeline Guard: Trap deployment anomalies before code alters customer routes
if [ \$? -ne 0 ]; then
    echo "❌ ERROR: Migrations failed! Deployment halted."
    exit 1
fi

echo "✅ Migrations successful. Starting the application..."
# Spin up production application instances alongside historical storage layers
docker compose up -d fastapi-app db

echo "--- Deployment Status ---"
docker compose ps
```

### Critical SRE Infrastructure Guarantees
*   **Zero Leak Environment Variables**: The dynamic formatting configuration pipeline (`awk` and `sed`) maps variables directly into active Bash memory channels. This completely prevents security leaks on remote host machines by eliminating physical `.env` files on disk.
*   **Migration Gateway Boundary (`--exit-code-from`)**: The deployment pipeline completely traps execution failures during schema upgrades. If an Alembic state transition returns an error, the execution chain exits (`exit 1`) immediately. This freezes the current operational code state, preventing rolling deployments from shipping broken endpoints to users.

---
