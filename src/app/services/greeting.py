def greeting_message(name: str) -> str:
    """Build a greeting independently of the Telegram transport."""
    return f"Hello, {name}! Use /help to see the available commands."
