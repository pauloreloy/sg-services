"""Domain enums for resource sharing service."""

from enum import Enum


class StepName(str, Enum):
    RESOURCE_SHARING = "RESOURCE_SHARING"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
