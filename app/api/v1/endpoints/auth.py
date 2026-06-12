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
from api.dependencies.rate_limiter import SlidingWindowLogAuthLimiter
# Services
from services.auth_service import AuthService
# Schemas
from schemas.user_schemas import UserCreateSchema, UserOutSchema, UserLoginSchema
from schemas.token_schemas import TokenOutSchema
# Settings
from core.settings import settings

user_auth_router = APIRouter(prefix='/auth', tags=["Users Auth"])

# Global Rate Limiting Guards Instantiations
signup_guard = SlidingWindowLogAuthLimiter(
    times=settings.redis.SIGNUP_LIMIT_TIMES,
    seconds=settings.redis.SIGNUP_LIMIT_SECONDS,
    endpoint_tag="signup"
)

login_guard = SlidingWindowLogAuthLimiter(
    times=settings.redis.LOGIN_LIMIT_TIMES,
    seconds=settings.redis.LOGIN_LIMIT_SECONDS,
    endpoint_tag="login"
)

refresh_guard = SlidingWindowLogAuthLimiter(
    times=settings.redis.REFRESH_LIMIT_TIMES,
    seconds=settings.redis.REFRESH_LIMIT_SECONDS,
    endpoint_tag="refresh"
)


@user_auth_router.post("/signup",
                       status_code=status.HTTP_201_CREATED,
                       response_model=UserOutSchema,
                       dependencies=[Depends(signup_guard)])
async def signup(user_create_data: UserCreateSchema,
                 user_auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> UserOutSchema:
    new_user = await user_auth_service.signup(user_create_data)
    return new_user


@user_auth_router.post("/login",
                       status_code=status.HTTP_200_OK,
                       response_model=TokenOutSchema,
                       dependencies=[Depends(login_guard)])
async def login(user_login_data: UserLoginSchema,
                response: Response,
                user_auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> TokenOutSchema:
    tokens = await user_auth_service.login(user_login_data, response=response)
    return tokens


@user_auth_router.post("/refresh",
                       status_code=status.HTTP_200_OK,
                       response_model=TokenOutSchema,
                       dependencies=[Depends(refresh_guard)])
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

    return await user_auth_service.refresh_tokens(refresh_token_str=refresh_token)


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
