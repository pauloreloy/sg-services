"""Configuration settings for share acceptance service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    aws_endpoint_url: str | None = "http://localhost:4566"

    # SQS
    sqs_source_queue_name: str = "share-acceptance"
    sqs_next_queue_name: str = "resource-links"
    sqs_failure_queue_name: str = "workflow-failed"
    sqs_wait_time_seconds: int = 10
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 30
    sqs_poll_interval_seconds: float = 1.0

    # DynamoDB
    dynamodb_table_name: str = "sg-share-governance"

    # App
    app_name: str = "sharegrant-share-acceptance-service"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
