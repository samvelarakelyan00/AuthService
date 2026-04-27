import re
from typing import Annotated

from pydantic import BaseModel, Field, EmailStr, AfterValidator


def validate_strong_password(v: str) -> str:
    checks = {
        r"[A-Z]": "at least one uppercase letter",
        r"[a-z]": "at least one lowercase letter",
        r"\d": "at least one number",
        r"[!@#$%^&*(),.?':{}|<>]": "at least one special character"
    }

    for pattern, message in checks.items():
        if not re.search(pattern, v):
            raise ValueError(f"Password must contain {message}")

    return v


StrongPassword = Annotated[
    str,
    Field(min_length=8, max_length=100),
    AfterValidator(validate_strong_password)
]


class BaseUserSchema(BaseModel):
    # username: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]
    username: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[EmailStr, Field(min_length=6, max_length=100)]

    model_config = {"from_attributes": True}


class UserCreateSchema(BaseUserSchema):
    # plain_password: StrongPassword
    plain_password: str


class UserOutSchema(BaseUserSchema):
    user_id: Annotated[int, Field(gt=0)]


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str
