import time
from typing import cast
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.bot.factory import create_dispatcher
from app.bot.handlers import framework, language, start


def update(update_id: int, text: str, user_id: int = 42) -> dict[str, object]:
    """Build a Telegram message update for dispatcher tests."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": int(time.time()),
            "text": text,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": f"User{user_id}"},
        },
    }


async def test_commands_and_survey_are_isolated(monkeypatch: pytest.MonkeyPatch, bot: Bot) -> None:
    send = AsyncMock(return_value=None)
    monkeypatch.setattr(Bot, "__call__", send)
    dispatcher = create_dispatcher(MemoryStorage())

    for index, command in enumerate(("/start", "/help", "/survey", "Python"), start=1):
        await dispatcher.feed_raw_update(bot, update(index, command))
    await dispatcher.feed_raw_update(bot, update(5, "/survey", user_id=99))
    await dispatcher.feed_raw_update(bot, update(6, "Aiogram"))
    await dispatcher.feed_raw_update(bot, update(7, "/cancel", user_id=99))

    messages = [call.args[0].text for call in send.await_args_list]
    assert "Hello, User42!" in messages[0]
    assert "/survey" in messages[1]
    assert messages[2] == "Which programming language do you use?"
    assert messages[3] == "Which framework do you use?"
    assert messages[5] == "Language: Python\nFramework: Aiogram"
    assert messages[6] == "Survey cancelled."


async def test_non_text_answer_reprompts(monkeypatch: pytest.MonkeyPatch, bot: Bot) -> None:
    send = AsyncMock(return_value=None)
    monkeypatch.setattr(Bot, "__call__", send)
    dispatcher = create_dispatcher(MemoryStorage())
    await dispatcher.feed_raw_update(bot, update(1, "/survey"))
    await dispatcher.feed_raw_update(
        bot,
        {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "date": int(time.time()),
                "sticker": {
                    "file_id": "file",
                    "file_unique_id": "unique",
                    "type": "regular",
                    "width": 1,
                    "height": 1,
                    "is_animated": False,
                    "is_video": False,
                },
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 42, "is_bot": False, "first_name": "User42"},
            },
        },
    )
    assert send.await_args_list[-1].args[0].text == "Please send a text answer or /cancel."


async def test_empty_answers_repeat_current_question() -> None:
    message = AsyncMock()
    message.text = "   "
    state = AsyncMock()
    await language(cast("Message", message), state)
    await framework(cast("Message", message), state)
    assert message.answer.await_count == 2
    state.set_state.assert_not_awaited()
    state.clear.assert_not_awaited()


async def test_start_ignores_message_without_user() -> None:
    message = AsyncMock()
    message.from_user = None
    await start(cast("Message", message))
    message.answer.assert_not_awaited()
