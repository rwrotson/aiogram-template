from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage

from app.bot.handlers import create_router
from app.bot.middleware import UpdateMiddleware


def create_dispatcher(storage: BaseStorage) -> Dispatcher:
    """Build an isolated dispatcher with the template's routers and middleware."""
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.outer_middleware(UpdateMiddleware())
    dispatcher.include_router(create_router())
    return dispatcher
