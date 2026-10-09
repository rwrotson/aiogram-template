from dataclasses import dataclass

from app.config import Settings
from app.infra.storage.base import StorageManager


@dataclass(frozen=True)
class AppContainer:
    """Hold the settings and storage manager owned by one application."""

    settings: Settings
    storage: StorageManager
