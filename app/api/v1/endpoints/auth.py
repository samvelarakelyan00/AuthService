# === Standard libs ===
from typing import (
    Annotated
)

# === Non-Standard libs ===
from fastapi import (
    APIRouter,
    Depends,
    status
)

# === Own Modules ===
# Dependencies
from core.dependencies import (
    get_auth_service
)
# Services
from services.auth_service import (
    AuthService
)
# Schemas
from schemas.user_schemas import (
    UserCreateSchema,
    UserOutSchema,
    UserLoginSchema
)

from schemas.token_schemas import (
    AccessTokenOutSchema
)


user_auth_router = APIRouter(prefix='/auth', tags=["Users Auth"])


@user_auth_router.post("/signup",
                       status_code=status.HTTP_201_CREATED,
                       response_model=UserOutSchema)
async def signup(user_create_data: UserCreateSchema,
                     user_auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> UserOutSchema:

    new_user = await user_auth_service.signup(user_create_data)

    return new_user


@user_auth_router.post("/login",
                       status_code=status.HTTP_200_OK,
                       response_model=AccessTokenOutSchema)
async def login(user_login_data: UserLoginSchema,
                     user_auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> AccessTokenOutSchema:

    access_token = await user_auth_service.login(user_login_data)

    return access_token
