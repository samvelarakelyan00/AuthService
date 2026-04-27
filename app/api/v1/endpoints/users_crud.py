# === Standard libs ===
from typing import List, Annotated

# === Non-Standard libs ===
from fastapi import APIRouter, Depends, status

# === Own Modules ===
from core.security import Security
# Dependencies
from core.dependencies import (
    get_current_user,
    get_user_crud
)

# Services
from services.users_crud import UserCRUD
# Schemas
from schemas.user_schemas import (
    UserOutSchema
)
from schemas.token_schemas import (
    AccessTokenBaseSchema
)


user_crud_router = APIRouter(tags=["Users CRUD"])


@user_crud_router.get("/users",
                      status_code=status.HTTP_200_OK,
                      response_model=List[UserOutSchema])
async def get_users(user_crud_service: Annotated[UserCRUD, Depends(get_user_crud)]):
    users = await user_crud_service.get_all_users()

    return users


@user_crud_router.get("/users/by-token",
                      status_code=status.HTTP_200_OK,
                      response_model=List[UserOutSchema])
async def get_users_by_token(user_crud_service: Annotated[UserCRUD, Depends(get_user_crud)],
                    access_token: AccessTokenBaseSchema = Depends(get_current_user)):
    users = await user_crud_service.get_all_users_by_token()

    return users