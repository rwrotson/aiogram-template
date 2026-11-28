from app.bot.replies import ERROR_REPLY, reply_for_error
from app.services.errors import ConflictError, FaqTopicNotFoundError, NotFoundError, ServiceError


class MissingItemError(NotFoundError):
    pass


class UnmappedError(ServiceError):
    pass


def test_subclass_inherits_base_reply() -> None:
    assert reply_for_error(MissingItemError()) == ERROR_REPLY[NotFoundError]


def test_generic_not_found_reply_has_no_faq_hint() -> None:
    assert "/faq" not in reply_for_error(NotFoundError())


def test_faq_topic_error_uses_faq_reply() -> None:
    assert reply_for_error(FaqTopicNotFoundError()) == ERROR_REPLY[FaqTopicNotFoundError]


def test_mapped_error_uses_its_own_reply() -> None:
    assert reply_for_error(ConflictError()) == ERROR_REPLY[ConflictError]


def test_unmapped_error_uses_generic_reply() -> None:
    assert reply_for_error(UnmappedError()) == ERROR_REPLY[ServiceError]
