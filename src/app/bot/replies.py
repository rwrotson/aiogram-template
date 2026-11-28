from app.services.errors import ConflictError, NotFoundError, ServiceError

ERROR_REPLY: dict[type[ServiceError], str] = {
    ServiceError: "Something went wrong. Try again later.",
    NotFoundError: "Unknown topic. Choose /faq commands or /faq storage.",
    ConflictError: "That conflicts with the current state. Try again later.",
}


def reply_for_error(exc: ServiceError) -> str:
    """Return the reply for the nearest mapped base class of a service error."""
    for cls in type(exc).__mro__:
        if cls in ERROR_REPLY:
            return ERROR_REPLY[cls]
    return ERROR_REPLY[ServiceError]
