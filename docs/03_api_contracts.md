# 🔌 Client Integration Hub & API Contract Specifications

This document defines the strict public network API contracts, data serialization formats, cryptographic token strategies, and error topologies for **AuthService v2**. It serves as the definitive reference manual for frontend developers, mobile engineers, and integration QA automation teams.

---

## 1. Hybrid Token Topology & Storage Matrix

To balance high-speed stateless authorization with strict server-side session control, the service enforces a hybrid token architecture designed to eliminate Cross-Site Scripting (XSS) and Cross-Site Request Forgery (CSRF) vulnerabilities.

| Security Layer | Transmission Vector | Expected Client Storage | Expiry Target (TTL) | Architecture Validation Method |
| :--- | :--- | :--- | :--- | :--- |
| **Access Token** | HTTP Authorization Header:<br>`Authorization: Bearer <JWT>` | Application Memory Space<br>(In-Memory State Variables) | **15 Minutes** *(1 min in local development)* | Completely Stateless.<br>Decoded via public HMAC-SHA256 configuration keys. |
| **Refresh Token** | Automated Browser Header:<br>`Set-Cookie: refresh_token=<Token>` | **HttpOnly, Secure, SameSite=Lax** Cookie | **30 Days** *(43,200 Minutes)* | Completely Stateful.<br>Obtains session status directly from Redis Whitelists. |

### 🔒 Cross-Origin Security Rules
*   **`HttpOnly`**: Enforced at the gateway. This completely blocks the client-side JavaScript engine (`document.cookie`) from intercepting or reading the refresh token payload, neutralizing XSS data theft.
*   **`Secure=True`**: Bound to configuration logic via `settings.ENV_STATE == "prod"`. This guarantees that the refresh token cookie is transmitted exclusively over encrypted HTTPS channels on production deployments, allowing non-HTTPS loops during local debugging cycles.
*   **`SameSite=Lax`**: Provides native browser protection against cross-site exploitation vectors, blocking third-party websites from reading active cookie states during automated script executions.

---

## 2. API v1 Endpoint Routing Matrix

The base path tracking signature for all primary endpoints is fixed at: `/api/v1`

```text
       [ Public Registration ] --------------------> POST /auth/signup
       [ Credentials Verification ] ---------------> POST /auth/login
       [ Concurrent Rotation Grace Pool ] ----------> POST /auth/refresh
       [ Distributed Device Eviction ] ------------> POST /auth/logout
       
       [ Protected Profile Verification ] ---------> GET  /users/by-token
```

### 2.1. Registration Pipeline: `POST /auth/signup`
Creates a fresh user profile entity inside the primary relational database.
*   **HTTP Success Code**: `211 Created`
*   **Request JSON Payload (`UserCreateSchema`)**:
```json
{
  "username": "senior_architect_2026",
  "email": "engineer@domain.com",
  "plain_password": "StrongPassword123!"
}
```
*   **Response JSON Payload (`UserOutSchema`)**:
```json
{
  "username": "senior_architect_2026",
  "email": "engineer@domain.com",
  "user_id": 1
}
```

### 2.2. Credentials Authorization Pipeline: `POST /auth/login`
Validates identity credentials, activates a state tracking row inside the Redis cluster cache, and provisions client authorization variables.
*   **HTTP Success Code**: `200 OK`
*   **Request JSON Payload (`UserLoginSchema`)**:
```json
{
  "email": "engineer@domain.com",
  "password": "StrongPassword123!"
}
```
*   **Response JSON Payload (`TokenOutSchema`)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OT..."
}
```
*   **Injected Transport Header (`Set-Cookie`)**:
```http
Set-Cookie: refresh_token=eyJhbGciOiJIUzI1...; Max-Age=2592000; Path=/; SameSite=Lax; HttpOnly; Secure
```

### 2.3. Token Rotation Pipeline: `POST /auth/refresh`
Exchanges the long-lived browser refresh cookie for a newly provisioned short-lived cryptographic Access Token.
*   **HTTP Success Code**: `200 OK`
*   **Request Parameters**: None. The route automatically extracts the cookie via an explicit `Annotated[str | None, Cookie()] = None` argument. If missing, it immediately aborts with an early `401` error.
*   **Response JSON Payload (`TokenOutSchema`)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OT..."
}
```

### 2.4. Session Demolition Pipeline: `POST /auth/logout`
Executes an idempotent session cleanup operation across both remote servers and local client storage engines.
*   **HTTP Success Code**: `204 No Content`
*   **Request Parameters**: Automatically parses the incoming `refresh_token` cookie.
*   **Response JSON Payload**: Empty Body.
*   **Injected Transport Header (`Set-Cookie`)**:
```http
Set-Cookie: refresh_token=; Max-Age=0; Path=/; SameSite=Lax; HttpOnly; Secure
```
*   *Note: Max-Age is zeroed out to force browser engines to drop the local token index entirely.*

### 2.5. Token Inspection Route (Internal Audit): `GET /users/by-token`
Allows downstream services or client layers to verify whether an Access Token matches a valid user account.
*   **HTTP Success Code**: `200 OK`
*   **Required Header Input**: `Authorization: Bearer <access_token>`
*   **Response JSON Payload (`List[UserOutSchema]`)**:
```json
[
  {
    "username": "senior_architect_2026",
    "email": "engineer@domain.com",
    "user_id": 1
  }
]
```

---

## 3. Concurrency Protection: The 15-Second Grace Buffer

Frontend developers must understand the runtime state lifecycle of the `/refresh` endpoint to handle complex web concurrency scenarios correctly.

```text
 Client Side (Parallel Requests)               AuthService Engine (Redis Mutator)
 +-----------------------------+               +----------------------------------+

  |--- (1) Request /page-data ---> [Expired API]
  |--- (2) Request /asset-list ---> [Expired API]
  |
  v (Frontend triggers Refresh interceptor)
  |=== (3) POST /auth/refresh -- (First) -------> Transition key to: "rotated" status
  |                                               Generates new Access + Refresh Token pair
  |                                               Starts active 15-second survival window
  |
  |=== (4) POST /auth/refresh -- (Second) ------> [Buffer Interception Zone]
                                                  Detects "rotated" status key state
                                                  Safely approves request within 15s window
                                                  Prevents broken client states/logout drops
```

### 🔄 Multi-Request Concurrency Behavior
When the frontend app encounters an expired Access Token across concurrent async requests (e.g., loading multiple components simultaneously), multiple refresh requests might hit the `/refresh` route at the exact same instant. 
1.  The first request to reach the server changes the token state inside Redis from `"active"` to `"rotated"`, applying an atomic 15-second survival timeout.
2.  Subsequent concurrent requests presenting the same token within that 15-second buffer are successfully approved, and return a valid access token.
3.  **Security Threat Boundary**: If a token with a `"rotated"` status hits the service after this 15-second grace window closes, it is flagged as a potential token reuse attack. The system logs a critical alert (`logger.critical(...)`) and immediately blocks the session.

---

## 4. Standardized Application Error Topology

All validation and authorization failures return structured error messages, ensuring predictable exception handling across client-side applications.

### 4.1. Error Payload Model Schema
```json
{
  "detail": "Detailed string parameter specifying the exact violation boundary condition context."
}
```

### 4.2. HTTP Status Code Mapping Matrix

#### `400 Bad Request`
*   **`Detail Payload`**: `"Username or email already registered."`
*   **Trigger Condition**: Fired during registration conflicts when an email address matches an existing entry inside the PostgreSQL database.

#### `401 Unauthorized`
*   **`Detail Payload`**: `"Refresh token missing from cookies"`
*   **Trigger Condition**: Fired when `/refresh` or `/logout` routes are executed without a valid cookie structure in the request headers.
*   **`Detail Payload`**: `"Invalid email or password"`
*   **Trigger Condition**: Fired when credentials fail verification, or when an email address is missing from the system. This route enforces a uniform latency delay using an internal Argon2id dummy hash.
*   **`Detail Payload`**: `"Token has expired"`
*   **Trigger Condition**: Fired when an Access Token has passed its expiration window. This signals the client application to run the `/refresh` routine.
*   **`Detail Payload`**: `"Token already rotated. Please reuse the new pair."`
*   **Trigger Condition**: Fired when a token with a `"rotated"` status is presented outside the permitted 15-second concurrency grace window.

---
