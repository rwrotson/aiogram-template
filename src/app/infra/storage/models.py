from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Subclass this base when adding application tables."""
