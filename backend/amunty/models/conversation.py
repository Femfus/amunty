"""Conversation model — a named chat session."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from amunty.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), default="New Chat", nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    # --- Odysseus Compatibility Properties ---
    owner: Mapped[str] = synonym("user_id")
    session_id: Mapped[str] = synonym("id")
    model: Mapped[str] = synonym("model_id")
    archived: Mapped[bool] = synonym("is_archived")

    @property
    def endpoint_url(self):
        return ""  # Stub for Odysseus compat
        
    @endpoint_url.setter
    def endpoint_url(self, value):
        pass
