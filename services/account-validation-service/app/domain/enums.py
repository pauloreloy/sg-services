"""Domain enums for account validation service."""

from enum import Enum


class StepName(str, Enum):
    ACCOUNT_VALIDATION = "ACCOUNT_VALIDATION"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
