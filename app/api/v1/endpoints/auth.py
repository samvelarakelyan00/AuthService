# === Standard libs ===
from typing import Annotated

# === Non-Standard libs ===
from fastapi import (
    APIRouter, Depends,
    status, Response, Cookie, HTTPException
)

# === Own Modules ===
# Dependencies
from api.dependencies import get_auth_service
# Services
from services.auth_service import AuthService
# Schemas
from schemas.user_schemas import UserCreateSchema, UserOutSchema, UserLoginSchema
from schemas.token_schemas import TokenOutSchema
# Rate Limiters
from api.dependencies.auth_deps.auth_rate_limiters_dep import (
    get_signup_rate_limiter,
    get_verify_email_rate_limiter,
    get_login_rate_limiter,
    get_refresh_token_rate_limiter
)


user_auth_router = APIRouter(prefix='/auth', tags=["Users Auth"])


@user_auth_router.post("/signup",
                       status_code=status.HTTP_201_CREATED,
                       response_model=UserOutSchema)
async def signup(user_create_data: UserCreateSchema,
                 user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
                 _: Annotated[None, Depends(get_signup_rate_limiter)]
) -> UserOutSchema:

    new_user = await user_auth_service.signup(user_create_data)
    return new_user


@user_auth_router.get("/verify-email/{token}",
                      status_code=status.HTTP_200_OK)
async def verify_email(
    token: str,
    user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
    _: Annotated[None, Depends(get_verify_email_rate_limiter)]
) -> dict:
    """
    Verify user's email address using a JWT verification token.
    The token is sent via email and contains the user_id and expiration.
    """
    return await user_auth_service.verify_email(token)


@user_auth_router.post("/login",
                       status_code=status.HTTP_200_OK,
                       response_model=TokenOutSchema)
async def login(user_login_data: UserLoginSchema,
                response: Response,
                user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
                _: Annotated[None, Depends(get_login_rate_limiter)]
) -> TokenOutSchema:

    tokens = await user_auth_service.login(user_login_data, response=response)
    return tokens


@user_auth_router.post("/refresh",
                       status_code=status.HTTP_200_OK,
                       response_model=TokenOutSchema)
async def refresh_token(
        response: Response,
        user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
        _: Annotated[None, Depends(get_refresh_token_rate_limiter)],
        refresh_token: Annotated[str | None, Cookie()] = None
) -> TokenOutSchema:

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookies"
        )

    return await user_auth_service.refresh_tokens(refresh_token_str=refresh_token, response=response)


@user_auth_router.post("/logout",
                       status_code=status.HTTP_204_NO_CONTENT)
async def logout(
        response: Response,
        user_auth_service: Annotated[AuthService, Depends(get_auth_service)],
        refresh_token: Annotated[str | None, Cookie()] = None
):

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookies"
        )

    await user_auth_service.logout(refresh_token_str=refresh_token)
    response.delete_cookie(key="refresh_token", path="/")
    return None
