from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import text, String, Boolean

from .base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True, index=True)

    username: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
