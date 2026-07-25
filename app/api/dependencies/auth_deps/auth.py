# === Standard libs ===
from typing import Any, Dict

# === Non-Standard libs ===
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# === Own Modules ===
from core.security import security
from api.dependencies.database import get_db
from schemas.user_schemas import UserOutSchema
from models import User


http_bearer = HTTPBearer()


async def get_current_user_data(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> Dict[str, Any]:
    """
    Lightweight dependency – returns user data from JWT payload.
    No database query – pure in‑memory operation.
    Use this when you need email/username but NOT the full DB object.
    """

    token = credentials.credentials

    try:
        payload = security.tokens.verify_token(token, expected_type="access")

        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "username": payload.get("username"),
            # "role": payload.get("role"),
            # "is_active": payload.get("is_active", True),
        }
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(err))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserOutSchema:
    """
    Heavyweight dependency – validates JWT, fetches full user from DB.
    Use this ONLY when you need the full user object.
    """
    user_data = await get_current_user_data(credentials)

    try:
        user_id = int(user_data.get("user_id"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token"
        )

    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return UserOutSchema.model_validate(user)
