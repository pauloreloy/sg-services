"""Domain exceptions.

These exceptions represent business rule violations and are raised by the
domain/application layers only. Infrastructure concerns (AWS errors, network
errors, etc.) must be translated into these exceptions (or handled) before
crossing into the application layer.
"""


class DomainError(Exception):
    """Base class for all domain-level errors."""


class InvalidMessagePayloadError(DomainError):
    """Raised when a queue message cannot be parsed or is missing required data."""
