# Standard libs
from typing import AsyncGenerator

# Non-Standard libs
from fastapi import Request

# Own Modules
from core.kafka.connection import kafka_manager
from services.event_service import EventService


async def get_kafka_producer(request: Request):
    if not kafka_manager.is_initialized:
        raise RuntimeError("Kafka connection manager not initialized.")

    return kafka_manager.producer


async def get_event_service() -> AsyncGenerator:
    yield EventService