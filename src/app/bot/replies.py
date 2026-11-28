from app.services.errors import ConflictError, FaqTopicNotFoundError, NotFoundError, ServiceError

ERROR_REPLY: dict[type[ServiceError], str] = {
    ServiceError: "Something went wrong. Try again later.",
    NotFoundError: "Not found.",
    FaqTopicNotFoundError: "Unknown topic. Choose /faq commands or /faq storage.",
    ConflictError: "That conflicts with the current state. Try again later.",
}


def reply_for_error(exc: ServiceError) -> str:
    """Return the reply for the nearest mapped base class of a service error."""
    return next(
        ERROR_REPLY[cls]
        for cls in type(exc).__mro__
        if issubclass(cls, ServiceError) and cls in ERROR_REPLY
    )
