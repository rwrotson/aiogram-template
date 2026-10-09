from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.services.greeting import greeting_message


class Survey(StatesGroup):
    """Collect two answers from one user in a chat."""

    language = State()
    framework = State()


async def start(message: Message) -> None:
    """Greet the user and point to the example commands."""
    if message.from_user is None:
        return
    await message.answer(greeting_message(message.from_user.first_name))


async def help_command(message: Message) -> None:
    """Describe the available commands."""
    await message.answer(
        "/start — greeting\n/help — commands\n/survey — two questions\n/cancel — stop the survey"
    )


async def cancel(message: Message, state: FSMContext) -> None:
    """Discard an unfinished survey."""
    await state.clear()
    await message.answer("Survey cancelled.")


async def survey(message: Message, state: FSMContext) -> None:
    """Start a two-question survey."""
    await state.set_state(Survey.language)
    await message.answer("Which programming language do you use?")


async def language(message: Message, state: FSMContext) -> None:
    """Store the first answer and ask the second question."""
    if message.text is None or not message.text.strip():
        await message.answer("Please send a non-empty text answer.")
        return
    await state.update_data(language=message.text.strip())
    await state.set_state(Survey.framework)
    await message.answer("Which framework do you use?")


async def framework(message: Message, state: FSMContext) -> None:
    """Finish the survey and clear its state."""
    if message.text is None or not message.text.strip():
        await message.answer("Please send a non-empty text answer.")
        return
    answers = await state.get_data()
    await state.clear()
    await message.answer(f"Language: {answers['language']}\nFramework: {message.text.strip()}")


async def text_required(message: Message) -> None:
    """Request text when a survey answer has another content type."""
    await message.answer("Please send a text answer or /cancel.")


def create_router() -> Router:
    """Register handlers on a fresh router for each application instance."""
    router = Router(name="examples")
    router.message.register(start, CommandStart())
    router.message.register(help_command, Command("help"))
    router.message.register(cancel, Command("cancel"))
    router.message.register(survey, Command("survey"))
    router.message.register(language, Survey.language, F.text)
    router.message.register(framework, Survey.framework, F.text)
    router.message.register(text_required, Survey.language)
    router.message.register(text_required, Survey.framework)
    return router
