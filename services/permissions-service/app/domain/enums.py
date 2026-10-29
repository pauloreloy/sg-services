"""Domain enums for permissions service."""

from enum import Enum


class StepName(str, Enum):
    PERMISSIONS = "PERMISSIONS"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
