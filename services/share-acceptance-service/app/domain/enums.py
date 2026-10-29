"""Domain enums for share acceptance service."""

from enum import Enum


class StepName(str, Enum):
    SHARE_ACCEPTANCE = "SHARE_ACCEPTANCE"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
