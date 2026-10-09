class MemoryFaqRepository:
    """Provide example FAQ answers from application-local memory."""

    def __init__(self) -> None:
        self._answers = {
            "commands": "Use /help to see all commands and /survey to try the FSM example.",
            "storage": "The bot uses memory by default. Configure Redis for persistent FSM state.",
        }

    def get(self, topic: str) -> str | None:
        """Return the answer associated with a topic."""
        return self._answers.get(topic)
