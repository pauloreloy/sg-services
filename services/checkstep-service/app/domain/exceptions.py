"""Domain-level exceptions."""


class GrantNotFoundError(Exception):
    """Raised when no processing record exists for the given grant_id."""


class StepNotFoundError(Exception):
    """Raised when no record exists for the requested step/attempt."""
