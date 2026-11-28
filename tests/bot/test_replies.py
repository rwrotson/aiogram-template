from app.bot.replies import ERROR_REPLY, reply_for_error
from app.services.errors import ConflictError, NotFoundError, ServiceError


class MissingTopicError(NotFoundError):
    pass


class UnmappedError(ServiceError):
    pass


def test_subclass_inherits_base_reply() -> None:
    assert reply_for_error(MissingTopicError()) == ERROR_REPLY[NotFoundError]


def test_mapped_error_uses_its_own_reply() -> None:
    assert reply_for_error(ConflictError()) == ERROR_REPLY[ConflictError]


def test_unmapped_error_uses_generic_reply() -> None:
    assert reply_for_error(UnmappedError()) == ERROR_REPLY[ServiceError]
