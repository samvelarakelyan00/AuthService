# Standard libs
import logging
from typing import Optional

# Non-Standard libs
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# Own Modules
from core.settings import settings


logger = logging.getLogger(__name__)


class KafkaConnectionManager:
    """
    Manages the lifecycle of the Kafka producer and consumer connections.

    Acts as a centralized container for Kafka operations, ensuring unified
    configuration, proper client initialization, and graceful shutdown.
    """

    def __init__(self) -> None:
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._is_initialized = False

    async def initialize(self) -> None:
        """
        Initializes the Kafka producer and consumer with configured settings.
        Should be called during application startup (lifespan).
        """
        if self._is_initialized:
            logger.warning("Kafka connection manager already initialized.")
            return

        logger.info("Initializing Kafka producer...")
        self._producer = self._create_producer()
        await self._producer.start()
        logger.info("Kafka producer started successfully.")

        self._is_initialized = True
        logger.info("Kafka connection manager fully initialized.")

    async def shutdown(self) -> None:
        """
        Gracefully closes all Kafka connections.
        Should be called during application shutdown (lifespan).
        """
        if not self._is_initialized:
            logger.warning("Kafka connection manager already shut down.")
            return

        if self._producer:
            logger.info("Shutting down Kafka producer...")
            await self._producer.stop()
            logger.info("Kafka producer stopped successfully.")

        if self._consumer:
            logger.info("Shutting down Kafka consumer...")
            await self._consumer.stop()
            logger.info("Kafka consumer stopped successfully.")

        self._is_initialized = False
        logger.info("Kafka connection manager fully shut down.")

    def _create_producer(self) -> AIOKafkaProducer:
        """Creates and configures the Kafka producer."""
        kafka_config = settings.kafka

        producer_kwargs = {
            "bootstrap_servers": kafka_config.BOOTSTRAP_SERVERS,
            "client_id": kafka_config.CLIENT_ID,
            "acks": -1,
            "compression_type": kafka_config.COMPRESSION_TYPE,
            "enable_idempotence": True,
            "retry_backoff_ms": 100,
            "request_timeout_ms": 30000,
        }

        # Add SASL/SSL if configured
        if kafka_config.SECURITY_PROTOCOL and kafka_config.SECURITY_PROTOCOL != "PLAINTEXT":
            producer_kwargs["security_protocol"] = kafka_config.SECURITY_PROTOCOL

            if kafka_config.SSL_CAFILE:
                producer_kwargs["ssl_cafile"] = kafka_config.SSL_CAFILE

            if kafka_config.SASL_USERNAME and kafka_config.SASL_PASSWORD:
                producer_kwargs["sasl_mechanism"] = kafka_config.SASL_MECHANISM
                producer_kwargs["sasl_plain_username"] = kafka_config.SASL_USERNAME.get_secret_value()
                producer_kwargs["sasl_plain_password"] = kafka_config.SASL_PASSWORD.get_secret_value()

        logger.debug(
            "Kafka producer configured",
            extra={
                "bootstrap_servers": kafka_config.BOOTSTRAP_SERVERS,
                "client_id": kafka_config.CLIENT_ID,
                "acks": -1,
                "compression": kafka_config.COMPRESSION_TYPE,
                "security_protocol": kafka_config.SECURITY_PROTOCOL,
                "enable_idempotence": True,
            }
        )

        return AIOKafkaProducer(**producer_kwargs)

    @property
    def producer(self) -> AIOKafkaProducer:
        """
        Returns the Kafka producer instance.
        Raises RuntimeError if not initialized.
        """
        if not self._is_initialized or self._producer is None:
            raise RuntimeError("Kafka producer not initialized. Call initialize() first.")

        return self._producer

    @property
    def is_initialized(self) -> bool:
        """Returns whether the connection manager is initialized."""
        return self._is_initialized


# Instantiate a single, global instance of the manager
kafka_manager = KafkaConnectionManager()