"""User model — single-user MVP."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from amunty.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
