# 🏛️ Architectural Specification & Domain Topography

This document establishes the official architectural blueprint, domain models, and infrastructure hardening protocols for **AuthService v2**. It is designed for Principal Architects, Lead Engineers, and Security Auditors to maintain structural continuity and data integrity across all operational environments.

---

## 1. System Topology & Architectural Principles

AuthService v2 adheres to an asynchronous, decoupled microservice pattern. The core engine separates runtime processing lanes to maximize raw network throughput while isolating state-heavy resources.

### Architectural Core Invariants

- **Stateless Token Transmission**: High-frequency API endpoints utilize completely stateless JWT signatures, discarding memory-heavy database lookup queries during routine payload validation cycles.
- **Stateful Session Revocation Lists**: Active sessions are bound to a stateful, sub-millisecond in-memory cache layer in Redis, allowing real-time session invalidation without the penalty of relational disk I/O.
- **Thread-Isolated Asymmetric Processing**: The single-threaded ASGI event loop is protected from heavy computational blocking. Execution flows split explicitly based on whether a task is I/O-bound (PostgreSQL/Redis) or CPU-bound (Argon2id cryptographic calculations).

---

## 2. Domain & Relational Persistence Topography

The domain data model maps clear boundary definitions between persistent database physical storage layers, application cache schemas, and serialization contracts.

```text
       [ Relational Schema: Postgres 16 ]           [ In-Memory Caching: Redis 7 ]
       +--------------------------------+           +----------------------------+
       |             users              |           |  Key String Validation     |
       |--------------------------------|           |----------------------------|
       | user_id (PK) : INT             |           | "auth:refresh:{uid}:{jti}" |
       | email (UQ)   : VARCHAR(100)    |           |   Value: "active"          |
       | username     : VARCHAR(100)    |           |   Value: "rotated" [15s]   |
       | hashed_pwd   : VARCHAR(1000)   |           +----------------------------+
       +--------------------------------+
                       |
                       | 1 : N (One-to-Many Audit Log)
                       v
       +--------------------------------+
       |         refresh_tokens         |
       |--------------------------------|
       | token_id (PK): INT             |
       | user_id (IX) : INT             |
       | token (IX,UQ): VARCHAR(512)    |
       | expires_at   : TIMESTAMP       |
       | is_revoked   : BOOLEAN         |
       | ip_address   : VARCHAR(45)     |
       | user_agent   : VARCHAR(255)    |
       +--------------------------------+
```

### 2.1 Table: `users`

Natively compiled via SQLAlchemy 2.0 declarative mappings. It enforces unique criteria at the hardware layer and establishes clean indexing routes for authorization search paths.

| Physical Column | Data Type | Database Constraints | Architectural / Security Purpose |
| :--- | :--- | :--- | :--- |
| **`user_id`** | `INTEGER` | Primary Key, Auto-Increment | System-wide unique identifier for upstream relational services. |
| **`username`** | `VARCHAR(100)` | Non-Null | Structural profile label identifier for application UI visibility. |
| **`email`** | `VARCHAR(100)` | Unique, Non-Null, B-Tree Index | Foundational login vector. Indexed explicitly for $O(1)$ query search performance during login operations. |
| **`hashed_password`** | `VARCHAR(1000)` | Non-Null | Custom capacity size to handle massive multi-byte Argon2id verification parameter strings seamlessly. |

### 2.2 Table: `refresh_tokens`

Stores physical session trails and system footprint telemetry parameters for security auditing, tracking active devices, and forensic analysis.

| Physical Column | Data Type | Database Constraints | Architectural / Security Purpose |
| :--- | :--- | :--- | :--- |
| **`token_id`** | `INTEGER` | Primary Key, Auto-Increment | Isolated database sequence tracking key. |
| **`user_id`** | `INTEGER` | Non-Null, B-Tree Index | Relational pointer mapping back to user profiles. Indexed for instant multi-device cascade revocations. |
| **`token`** | `VARCHAR(512)` | Unique, Non-Null, B-Tree Index | Cryptographic payload mapping key, optimized for rapid, collision-free transaction search operations. |
| **`expires_at`** | `TIMESTAMP` | Non-Null | Hard database timestamp indicating session lifecycle boundaries. |
| **`is_revoked`** | `BOOLEAN` | Server Default: `false` | Fallback boolean flag to explicitly invalidate stolen or manually blacklisted administrative records. |
| **`created_at`** | `TIMESTAMP` | Server Default: `NOW()` | Read-only structural database creation log for system auditing timelines. |
| **`user_agent`** | `VARCHAR(255)` | Nullable | Captures incoming application signatures to detect sudden changes in user client runtime software. |
| **`ip_address`** | `VARCHAR(45)` | Nullable | Captures full-range client addresses. 45-character allocation fully accommodates uncompressed IPv6 paths. |

---

## 3. Core Hardening Protocols & Security Engineering

The service's defensive landscape is engineered directly into its business execution layer, ensuring cryptographic integrity and protection against common attack vectors.

### 3.1 Timing Attack Mitigation & Latency Padding

**The Threat**: Argon2id functions are computationally heavy by design (~100–200ms processing duration). If an API evaluates an invalid login email and instantly drops the connection frame with a `401` in 5ms, but takes 150ms to verify a valid user's password hash, malicious actors can easily enumerate valid user registration rosters via timing signature discrepancies.

**The Implementation (`services/auth_service.py`)**: When a lookup query returns no valid record matching the targeted email address, the system purposefully suppresses a premature exit. It executes a synthetic verification pipeline against a pre-compiled cryptographic dummy hash payload string:

```python
# Fully structured template Argon2id dummy block to enforce latency parity
dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$dGVzdHBhc3N3b3Jk"
await run_in_threadpool(
    self.security.passwords.verify,
    user_login_data.password,
    dummy_hash
)
```

This routine enforces absolute clock timing uniformity across all `/login` API response streams, completely neutralizing network latency profile scanning.

### 3.2 Non-Blocking Asynchronous Threadpool Isolation

**The Threat**: Hashing engines are designed to maximize CPU saturation to prevent high-speed brute-force attacks. However, running a heavy CPU-bound payload inside an asynchronous framework completely starves the single-threaded event loop (`Event Loop`), blocking it from executing simultaneous I/O tasks and causing a systemic Denial of Service (DoS) event.

**The Implementation**: All cryptographic password evaluations are cleanly extracted from the primary runtime flow and delegated directly to detached thread networks managed through an optimized asynchronous pool worker interface:

```python
# Threadpool execution prevents Event Loop starvation
hashed_password = await run_in_threadpool(
    self.security.passwords.hash,
    user_create_data.plain_password
)
```

This ensures the ASGI server event loop remains free to process incoming high-speed network traffic while background threads absorb the heavy cryptographic computations.

### 3.3 Atomic Session Management & Token Rotation Grace Buffer

**The Threat**: Modern web client runtimes often fire concurrent, parallel asset requests on initial boot or page refresh frames. If an access token expires, multiple requests may hit the `/refresh` endpoint simultaneously. If the first incoming request immediately evicts the old refresh token from the cache, the subsequent parallel requests will fail, triggering unintended user logouts.

**The Implementation**: Token rotation logic utilizes an atomic Redis transactional environment pipeline to safely handle front-end race conditions:

```python
# Atomic Pipeline Transaction protects concurrent consumer requests
async with self.redis.pipeline(transaction=True) as pipe:
    # Retain the parent JTI key with a 15-second survival threshold
    await pipe.set(old_redis_key, "rotated", ex=15)
    # Provision the fresh child JTI token record status immediately
    await pipe.set(new_redis_key, "active", ex=new_refresh_data["ttl_seconds"])
    await pipe.execute()
```

- **The 15-Second Grace Window**: Incoming requests presenting a `"rotated"` status token within this 15-second buffer are safely accommodated, preventing broken client states.
- **Intrusion Detection Trigger**: If a token with a `"rotated"` status is reused after this grace period concludes, the system fires an explicit `logger.critical(...)` alert flag. This signals a potential token-replay attack, indicating that an evicted token has been intercepted and reused by a malicious actor.

---

## 4. Lifecycle & Graceful Teardown Sequence

The operational lifespan of external dependencies is strictly regulated via an asynchronous context lifecycle wrapper loop (`lifespan`) attached directly to the core ASGI application object.

```text
 [ Lifecycle Boot Frame ]
            |
            +---> 1. Initialize Logging Configuration Subsystem
            +---> 2. Construct Shared State Connections Containers
            +---> 3. PostgreSQL Probe: Execute Isolated "SELECT 1" (Fail-Fast Guard)
            +---> 4. Redis Probe: Execute Distributed "PING" (Fail-Fast Guard)
            |
    ===================================================
    ===================================================
     MICROSERVICE RUNTIME LAYER: ACTIVE FOR TRAFFIC
    ===================================================
            |
 [ Graceful Teardown Sequence Triggered ]
            |
            +---> 5. Dispose SQLAlchemy Database Engine Pools
            +---> 6. Terminate Active Redis Client Connections
            +---> 7. Disconnect Redis Pool Sockets
            |
 [ Core System Halt Concluded Cleanly ]
```

### 4.1 Fail-Fast Infrastructure Initialization

Rather than starting in a partially degraded state, the service validates its structural connection parameters immediately upon boot. If either the PostgreSQL engine pool or the Redis cache sockets drop or reject the network connection frame, the system intercepts the error, writes a critical exception log dump, and executes a full startup halt (`raise error`). This fail-fast pattern ensures container orchestrators (such as Kubernetes pods) immediately identify deployment failures and prevent broken containers from receiving live routing traffic.

### 4.2 Resource Teardown Integrity

When a termination signal (`SIGTERM` / `SIGINT`) is received, the application initiates an orderly teardown sequence. By explicitly disposing of the SQLAlchemy engine connection pool and disconnecting all active Redis socket layers via the post-yield lifespan loop block, the service prevents orphaned connections, avoids socket leaks at the OS level, and allows downstream database clusters to recycle resources immediately.

---

> **Next Document: `02_operations.md` — Operational Matrix & DevOps Deployments**

---