"""Async database engine, session factory, and initialization."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from amunty.config import settings

logger = logging.getLogger("amunty.database")

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables and enable WAL mode for SQLite."""
    from sqlalchemy import text

    from amunty.models import Base  # noqa: F811

    async with engine.begin() as conn:
        # Enable WAL mode for SQLite (better concurrent read performance)
        if "sqlite" in settings.database_url:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))

        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized: %s", settings.database_url)
