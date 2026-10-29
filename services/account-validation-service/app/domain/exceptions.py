"""Domain exceptions for account validation."""


class InvalidMessagePayloadError(Exception):
    """Raised when incoming message lacks required contract attributes."""


class AccountNotEligibleError(Exception):
    """Raised when the consumer account or producer account is ineligible or unauthorized."""
