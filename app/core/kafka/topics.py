# Standard libs
from enum import StrEnum


class KafkaTopics(StrEnum):
    EMAIL_EVENTS = "auth.email.events"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Returns all topic names for consumer subscription."""
        return [topic.value for topic in cls]