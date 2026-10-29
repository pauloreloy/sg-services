"""Domain exceptions."""


class DomainError(Exception):
    """Base class for all domain-level errors."""


class GrantNotFoundError(DomainError):
    """Raised when no processing record exists for a given grant_id."""

    def __init__(self, grant_id: str) -> None:
        self.grant_id = grant_id
        super().__init__(f"No record found for grant_id='{grant_id}'.")
