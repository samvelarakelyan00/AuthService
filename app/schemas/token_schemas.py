from typing import Annotated, Literal

from pydantic import BaseModel, Field, EmailStr, RootModel


class AccessTokenOutSchema(RootModel[Annotated[str, Field(min_length=20, max_length=265)]]):
    pass


class RefreshTokenOutSchema(RootModel[Annotated[str, Field(min_length=20, max_length=265)]]):
    pass


class TokenOutSchema(BaseModel):
    access_token: AccessTokenOutSchema
    refresh_token: RefreshTokenOutSchema
    token_type: Annotated[Literal["Bearer"], "Tokens type"] = "Bearer"


class AccessTokenPayloadDataSchema(BaseModel):
    user_id: str
    user_email: EmailStr
