# === Standard libs ===
from typing import Dict, Any

# === Non-Standard libs ===
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# === Own Modules ===
from core.dependencies.database import get_db
from core.dependencies.security import get_security
from core.security import Security
from models.users import User
from schemas.user_schemas import UserOutSchema


http_bearer = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
        db: AsyncSession = Depends(get_db),
        security: Security = Depends(get_security)
) -> UserOutSchema:

    token = credentials.credentials

    try:
        payload = security.verify_token(token, expected_type="access")

        user_id_str = payload.get("sub")

        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is missing subject"
            )

        user_id = int(user_id_str)

    except ValueError as e:
        # Сюда попадут ошибки: "Token has expired", "Invalid token", "Invalid token type"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except TypeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier format"
        )

    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Проверка флага активности (раскомментируйте, если поле is_active добавлено в модель)
    # if not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Account is deactivated"
    #     )

    print(f"User with user_id {user_id} wants to get data!")

    return UserOutSchema.model_validate(user)
