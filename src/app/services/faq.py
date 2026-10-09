from typing import Protocol

from app.services.errors import NotFoundError


class FaqRepository(Protocol):
    """Read answers by topic without depending on their storage."""

    def get(self, topic: str) -> str | None:
        """Return the answer for a topic when it exists."""
        ...


class FaqService:
    """Look up FAQ topics for Telegram and other interfaces."""

    def __init__(self, repository: FaqRepository) -> None:
        self._repository = repository

    def answer(self, topic: str) -> str:
        """Return a topic answer or report that it is unknown."""
        answer = self._repository.get(topic)
        if answer is None:
            raise NotFoundError(topic)
        return answer
