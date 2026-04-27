from typing import Annotated, Literal

from pydantic import BaseModel, Field, EmailStr


class AccessTokenBaseSchema(BaseModel):
    access_token: Annotated[str, Field(min_length=20, max_length=265)]


class AccessTokenOutSchema(AccessTokenBaseSchema):
    token_type: Annotated[str, Literal["Bearer"]]


class AccessTokenPayloadDataSchema(BaseModel):
    user_id: str
    user_email: EmailStr