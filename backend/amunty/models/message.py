"""Message model — a single message in a conversation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from amunty.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "user", "assistant", "system", "tool"
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    # --- Odysseus Compatibility Properties ---
    session_id: Mapped[str] = synonym("conversation_id")
    timestamp: Mapped[datetime] = synonym("created_at")
