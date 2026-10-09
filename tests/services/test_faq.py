from unittest.mock import Mock

import pytest

from app.services.errors import NotFoundError
from app.services.faq import FaqService


def test_faq_service_returns_repository_answer() -> None:
    repository = Mock()
    repository.get.return_value = "Answer"

    assert FaqService(repository).answer("commands") == "Answer"
    repository.get.assert_called_once_with("commands")


def test_faq_service_reports_unknown_topic() -> None:
    repository = Mock()
    repository.get.return_value = None

    with pytest.raises(NotFoundError, match="missing"):
        FaqService(repository).answer("missing")
