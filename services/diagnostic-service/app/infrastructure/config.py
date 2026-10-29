"""Configuration settings for diagnostic service."""

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
    sqs_completed_queue_name: str = "workflow-completed"
    sqs_failed_queue_name: str = "workflow-failed"
    sqs_wait_time_seconds: int = 10
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 30
    sqs_poll_interval_seconds: float = 1.0

    # Step Functions
    sfn_state_machine_name: str = "GovernanceDiagnosticWorkflow"

    # SNS
    sns_notifications_topic_name: str = "sg-governance-notifications"

    # CheckStep HTTP URL
    checkstep_service_url: str = "http://localhost:8080"

    # App
    app_name: str = "sharegrant-diagnostic-service"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
