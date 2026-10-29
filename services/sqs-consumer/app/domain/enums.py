"""Enumerations shared across the domain layer."""

from enum import Enum


class ProcessingStatus(str, Enum):
    """Outcome of processing a message received from the queue."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
