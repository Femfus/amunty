"""SQLAlchemy model base and common mixins."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all models."""

    pass
