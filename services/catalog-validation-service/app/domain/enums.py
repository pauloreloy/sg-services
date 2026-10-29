"""Domain enums for catalog validation service."""

from enum import Enum


class StepName(str, Enum):
    CATALOG_VALIDATION = "CATALOG_VALIDATION"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
