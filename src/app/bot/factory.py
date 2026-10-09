from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseEventIsolation, BaseStorage
from aiogram.fsm.storage.memory import SimpleEventIsolation

from app.bot.handlers import create_router
from app.bot.middleware import UpdateMiddleware


def create_dispatcher(
    storage: BaseStorage, events_isolation: BaseEventIsolation | None = None
) -> Dispatcher:
    """Build an isolated dispatcher with the template's routers and middleware."""
    dispatcher = Dispatcher(
        storage=storage,
        events_isolation=events_isolation
        if events_isolation is not None
        else SimpleEventIsolation(),
    )
    dispatcher.update.outer_middleware(UpdateMiddleware())
    dispatcher.include_router(create_router())
    return dispatcher
