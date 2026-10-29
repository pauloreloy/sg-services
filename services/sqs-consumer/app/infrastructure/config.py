"""Application configuration, loaded from environment variables / .env file.

Centralizing configuration here keeps AWS/infra specific settings out of the
domain and application layers (hexagonal architecture - the "ports" do not
need to know how adapters are configured).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. All values can be overridden via environment vars."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AWS generic ---
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    # Set to a LocalStack URL (e.g. http://localhost:4566) for local runs.
    # Leave unset/None to talk to real AWS.
    aws_endpoint_url: str | None = "http://localhost:4566"

    # --- SQS ---
    sqs_source_queue_name: str = "sg-share-queue"
    sqs_success_queue_name: str = "sg-share-success-queue"
    sqs_failure_queue_name: str = "sg-share-failure-queue"
    sqs_wait_time_seconds: int = 10
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 30
    sqs_poll_interval_seconds: float = 1.0

    # --- DynamoDB ---
    dynamodb_table_name: str = "sg-share-processing-records"

    # --- App ---
    app_name: str = "sharegrant-sqs-consumer"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of :class:`Settings`."""
    return Settings()
