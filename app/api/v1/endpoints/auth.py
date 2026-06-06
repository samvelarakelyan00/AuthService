# === Standard libs ===
from typing import Annotated

# === Non-Standard libs ===
from fastapi import (
    APIRouter, Depends,
    status, Response, Cookie, HTTPException  # Added Cookie and Response
)

# === Own Modules ===
# Dependencies
from api.dependencies import (
    get_auth_service
)
# Services
from services.auth_service import (
    AuthService
)
# Schemas
from schemas.user_schemas import (
    UserCreateSchema, UserOutSchema,
    UserLoginSchema
)
from schemas.token_schemas import (
    TokenOutSchema
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
                       response_model=TokenOutSchema)
async def login(user_login_data: UserLoginSchema,
                response: Response,
                user_auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> TokenOutSchema:
    tokens = await user_auth_service.login(user_login_data, response=response)
    return tokens


@user_auth_router.post("/refresh",
                       status_code=status.HTTP_200_OK,
                       response_model=TokenOutSchema)
async def refresh_token(
        response: Response,
        user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
        refresh_token: Annotated[str | None, Cookie()] = None
) -> TokenOutSchema:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookies"
        )

    # Passing token down to service (Later we can inject response here too for Token Rotation)
    return await user_auth_service.refresh_tokens(refresh_token_str=refresh_token)


@user_auth_router.post("/logout",
                       status_code=status.HTTP_204_NO_CONTENT)
async def logout(
        response: Response,
        user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
        refresh_token: Annotated[str | None, Cookie()] = None
):
    """
    Logout. Removes the Refresh token from Redis and clears the cookie on the client.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookies"
        )

    await user_auth_service.logout(refresh_token_str=refresh_token)

    # Erase the cookie from the client browser completely
    response.delete_cookie(key="refresh_token", path="/")
    return None
