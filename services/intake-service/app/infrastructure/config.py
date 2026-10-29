"""Configuration settings for intake service."""

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
    sqs_first_queue_name: str = "access-validation"

    # DynamoDB
    dynamodb_table_name: str = "sg-share-governance"

    # S3
    s3_payload_bucket: str = "sg-governance-payloads"

    # App
    app_name: str = "sharegrant-intake-service"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
