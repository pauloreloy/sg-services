"""Enumerations shared across the domain layer."""

from enum import Enum


class ProcessingStatus(str, Enum):
    """Mirrors the status values persisted by the sqs-consumer service."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
