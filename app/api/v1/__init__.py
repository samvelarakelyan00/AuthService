from fastapi import APIRouter

from .endpoints.auth import user_auth_router
from .endpoints.users_crud import user_crud_router


v1_router = APIRouter(prefix="/v1")


v1_router.include_router(user_auth_router)
v1_router.include_router(user_crud_router)
