# === Standard libs ===
# ...

# === Non-Standard libs ===
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# === Own Modules ===
from core.dependencies.database import get_db
from core.dependencies.security import get_security
from core.security import Security
from models import User
from schemas.user_schemas import UserOutSchema

http_bearer = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
        db: AsyncSession = Depends(get_db),
        security: Security = Depends(get_security)
) -> UserOutSchema:
    """Get current authenticated user"""
    token = credentials.credentials

    try:
        payload = security.verify_access_token(token)


        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = int(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    # Get user from database
    result = await db.execute(text("""SELECT *
                                      FROM users
                                      WHERE user_id = :user_id"""),
                              {"user_id": user_id})

    user = result.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    print(f"User with user_id {user_id} wants to get data!")

    # if not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Account is deactivated"
    #     )

    return UserOutSchema.model_validate(user)
