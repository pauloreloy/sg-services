"""Domain enums for resource link service."""

from enum import Enum


class StepName(str, Enum):
    RESOURCE_LINKS = "RESOURCE_LINKS"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
