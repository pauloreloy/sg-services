"""Application configuration, loaded from environment variables / .env file."""

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

    # --- DynamoDB ---
    dynamodb_table_name: str = "sg-share-processing-records"
    dynamodb_grant_id_index_name: str = "grant_id-processed_at-index"
    dynamodb_governance_table_name: str = "sg-share-governance"

    # --- App ---
    app_name: str = "sharegrant-checkstep-service"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of :class:`Settings`."""
    return Settings()
