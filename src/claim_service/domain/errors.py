"""Domain errors. REST maps them to HTTP status codes; MCP tools return them as tool errors."""


class DomainError(Exception):
    """Base class for errors that are caused by the request, not by the server."""


class NotFoundError(DomainError):
    """A referenced user, policy or rider does not exist for this user."""


class ConflictError(DomainError):
    """The request conflicts with existing data (for example, the user already exists)."""


class DuplicateRiderError(ConflictError):
    """The same rider name was given twice under one policy."""


class InvalidMappingError(DomainError):
    """A rider mapping does not satisfy the standard rule or custom condition requirements."""


class AccessDeniedError(DomainError):
    """The user_id belongs to another user or the PIN / bound API key does not match."""

