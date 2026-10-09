class ServiceError(Exception):
    """Base class for expected use-case failures reported by bot handlers."""


class NotFoundError(ServiceError):
    """The requested resource does not exist."""


class ConflictError(ServiceError):
    """An operation conflicts with the current state of a resource."""
