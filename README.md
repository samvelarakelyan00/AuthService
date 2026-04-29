# High-performance authentication microservice
## ***UNDER CONSTRUCTION !!!***

---

### High-performance authentication microservice with

---

- **FastAPI** 
- **featuring JWT authentication**
- **secure password hashing**
- **RBAC**
- **PostgreSQL integration**

---
***Implemented third-party OAuth authentication (Google, Apple),
database migrations with Alembic, and a clean, scalable architecture.***

## 🚀 Quick Start (Docker)
1. **Clone the repository:**
    ```bash
   git clone git@github.com:samvelarakelyan00/AuthService.git
   cd AuthService/
   ```
2. **Setup Environment:**
   Create a `.env` file based on `.env.example`.
3. **Run with Docker Compose:**
   ```bash
   docker compose up -d --build
   ```
4. **Access Documentation:**
   Open [http://0.0.0.0:8000/docs](http://0.0.0.0:8000/docs) to access Swagger UI.

---

## 🏗️ Project Structure
Following best practices, the project is structured to be scalable:

```text
├── app/
│   ├── alembic/        # Database migrations (Alembic)
│   ├── api/            # API versioning and route endpoints (v1)
│   │   ├── v1/         # API versioning
│   │   __init__.py     # Endpoints
│   ├── core/           # Config, security, exceptions, and dependencies
│   ├── db/             # Database connection and session management
│   ├── models/         # Database models (SQLAlchemy/SQLModel)
│   ├── schemas/        # Pydantic models for request/response validation
│   ├── services/       # Core business logic
│   ├── tasks/          # Background tasks (e.g., Celery/Arq)
│   ├── utils/          # Shared helper functions and utilities
│   ├── alembic.ini     # Alembic configuration
│   └── main.py         # Application entry point
├── tests/              # Test suite (Integration and Unit tests)
├── .env.example        # Template for environment variables
├── deploy.sh           # Deployment automation script
├── Dockerfile          # Container definition
├── docker-compose.yml  # Local development orchestration
├── pyproject.toml      # Build system and dependency management
└── uv.lock             # Deterministic lockfile (managed by uv)
```

## 🛠️ Tech Stack
- **FastAPI**: High-performance web framework.
- **SQLModel / SQLAlchemy**: ORM for database interactions.
- **PostgreSQL**: Database.
- **Redis**: For caching and rate limiters
- **Docker / Docker Compose**: Containerization.
- **Pytest**: Testing framework.

---

## 🧪 Testing
***UNDER CONTRUCTION !!! NOT WORKING YET!!!***
```bash
docker-compose exec app pytest
```

## 🔐 Environment Variables
**Find all the list of environment variables `/AuthService/.env.example` file in**.