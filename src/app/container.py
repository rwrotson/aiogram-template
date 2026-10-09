from dataclasses import dataclass

from app.config import Settings
from app.infra.storage.base import StorageManager
from app.services.faq import FaqService


@dataclass(frozen=True)
class AppContainer:
    """Hold settings and services owned by one application."""

    settings: Settings
    storage: StorageManager
    faq: FaqService
