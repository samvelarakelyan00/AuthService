# Standard libs
import logging

# Non-Standard libs
from fastapi import HTTPException, status

# Own Modules
from core.kafka.connection import kafka_manager
from core.kafka.topics import KafkaTopics
from schemas.event_schemas import (
    EventMetadata,
    EmailVerificationEvent,
    EmailVerificationEventData,
    EmailEventTypes,
)


logger = logging.getLogger(__name__)


class EventService:
    """
    Orchestrates publishing of domain events to Kafka.
    Acts as a thin wrapper around the Kafka producer.
    """

    @staticmethod
    async def publish_email_verification(
        user_id: int,
        email: str,
        username: str,
        verification_token: str,
        expires_in_hours: int = 72,
    ) -> None:
        """
        Publishes an email verification event to Kafka.
        The email service (consumer) will handle sending the actual email.
        """
        logger.info(
            "Publishing email verification event for user_id: '%s', email: '%s'",
            user_id,
            email,
        )

        # Ensure Kafka is initialized
        if not kafka_manager.is_initialized:
            logger.critical(
                "Kafka connection manager not initialized. Cannot publish event."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Message queue service unavailable. Please try again later.",
            )

        # Build the event payload
        event_data = EmailVerificationEventData(
            user_id=user_id,
            email=email,
            username=username,
            verification_token=verification_token,
            expires_in_hours=expires_in_hours,
        )

        event = EmailVerificationEvent(
            metadata=EventMetadata(
                event_type=EmailEventTypes.VERIFICATION,
            ),
            data=event_data,
        )

        # ✅ Serialize to JSON using Pydantic's model_dump_json() (handles datetime)
        event_json = event.model_dump_json()
        event_bytes = event_json.encode("utf-8")

        try:
            # Publish to Kafka
            producer = kafka_manager.producer
            await producer.send_and_wait(
                topic=KafkaTopics.EMAIL_EVENTS.value,
                value=event_bytes,
                key=str(user_id).encode("utf-8"),
            )
            logger.debug(
                "Email verification event published successfully. Topic: '%s', Event ID: '%s'",
                KafkaTopics.EMAIL_EVENTS.value,
                event.metadata.event_id,
            )

        except Exception as exc:
            logger.error(
                "Failed to publish email verification event: %s",
                str(exc),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to send verification email. Please try again later.",
            )