from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from services.users_crud import UserCRUD
from services.auth_service import AuthService

from core.security import Security
from core.dependencies.security import get_security


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    security: Security = Depends(get_security)
) -> AuthService:
    return AuthService(db, security)


async def get_user_crud(db: AsyncSession = Depends(get_db)):
    return UserCRUD(db)
