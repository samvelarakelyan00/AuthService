# # === Standard libs ===
#
# # === Non-Standard libs ===
# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
#
# # === Own Modules ===
# from api.dependencies.database import get_db
# from api.dependencies.security import get_security
# from core.security import Security
# from models import User
# from schemas.user_schemas import UserOutSchema
#
#
# http_bearer = HTTPBearer()
#
#
# async def get_current_user(
#         credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
#         db: AsyncSession = Depends(get_db),
#         security: Security = Depends(get_security)
# ) -> UserOutSchema:
#
#     token = credentials.credentials
#
#     try:
#         payload = security.tokens.verify_token(token, expected_type="access")
#
#         user_id_str = payload.get("sub")
#
#         if not user_id_str:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Token payload is missing subject"
#             )
#
#         user_id = int(user_id_str)
#
#     except ValueError as e:
#         # Сюда попадут ошибки: "Token has expired", "Invalid token", "Invalid token type"
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(e)
#         )
#     except TypeError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid user identifier format"
#         )
#
#     stmt = select(User).where(User.user_id == user_id)
#     result = await db.execute(stmt)
#     user: User | None = result.scalar_one_or_none()
#
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found"
#         )
#
#     print(f"User with user_id {user_id} wants to get data!")
#
#     return UserOutSchema.model_validate(user)



# === Standard libs ===

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


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> str:
    """
    Lightweight dependency – only validates JWT and returns user_id.
    No database query – pure in‑memory operation.
    Use this for most endpoints that only need the user ID.
    """
    token = credentials.credentials

    try:
        payload = security.tokens.verify_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Token missing subject")
        return user_id
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(err))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserOutSchema:
    """
    Heavyweight dependency – validates JWT, fetches full user from DB.
    Use this ONLY when you need the full user object.
    """
    user_id_str = await get_current_user_id(credentials)

    try:
        user_id = int(user_id_str)
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