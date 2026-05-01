from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import String, DateTime, Boolean, text

from .base import Base


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    token_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
