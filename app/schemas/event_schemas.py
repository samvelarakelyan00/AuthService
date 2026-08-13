# Standard libs
import uuid
from datetime import datetime

# Non-Standard libs
from pydantic import BaseModel, Field, EmailStr


class EventMetadata(BaseModel):
    """Common metadata for all events."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = "auth-service"
    version: str = "1.0"


class EmailVerificationEventData(BaseModel):
    """Data payload for email verification events."""
    user_id: int
    email: EmailStr
    username: str
    verification_token: str
    expires_in_hours: int = Field(default=72)


class EmailVerificationEvent(BaseModel):
    """Complete email verification event structure."""
    metadata: EventMetadata
    data: EmailVerificationEventData


class EmailEventTypes:
    """Centralized email event type definitions."""
    VERIFICATION = "email.verification"
    WELCOME = "email.welcome"
    PASSWORD_RESET = "email.password_reset"
    PASSWORD_RESET_CONFIRMATION = "email.password_reset_confirmation"
    MAGIC_LINK = "email.magic_link"  # passwordless authentication method, Single use for