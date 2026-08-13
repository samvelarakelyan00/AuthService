# Non-Standard libs
from pydantic import BaseModel, Field, SecretStr


class KafkaSettings(BaseModel):
    """
    Structured validation namespace for Kafka connection parameters.
    """
    BOOTSTRAP_SERVERS: str = Field(default="localhost:9092")
    CLIENT_ID: str = Field(default="auth-service")
    GROUP_ID: str = Field(default="auth-service-group")
    ENABLE_AUTO_COMMIT: bool = Field(default=False)
    AUTO_OFFSET_RESET: str = Field(default="earliest")  # earliest | latest | none

    # Security (SASL/SSL) - optional for production
    SECURITY_PROTOCOL: str = Field(default="PLAINTEXT")  # PLAINTEXT | SASL_SSL | SSL
    SASL_MECHANISM: str = Field(default="PLAIN")  # PLAIN | SCRAM-SHA-256 | SCRAM-SHA-512
    SASL_USERNAME: SecretStr | None = Field(default=None)
    SASL_PASSWORD: SecretStr | None = Field(default=None)
    SSL_CAFILE: str | None = Field(default=None)

    # Producer-specific
    ACKS: int = Field(default=-1)  # 1, 0, -1
    BATCH_SIZE: int = Field(default=16384)  # 16KB
    LINGER_MS: int = Field(default=10)  # 10ms
    COMPRESSION_TYPE: str = Field(default="gzip") # none, gzip, snappy, lz4, zstd

    # Consumer-specific
    MAX_POLL_RECORDS: int = Field(default=500)
    SESSION_TIMEOUT_MS: int = Field(default=45000)
    HEARTBEAT_INTERVAL_MS: int = Field(default=3000)
    MAX_PARTITION_FETCH_BYTES: int = Field(default=1048576)  # 1MB