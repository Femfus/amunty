"""Settings models — model backends and app-wide key-value settings."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from amunty.models.base import Base


class ModelConfig(Base):
    """A configured model backend (e.g., Ollama at localhost:11434)."""

    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    backend_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "ollama", "openai", "vllm", "llamacpp"
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # Display name
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Fernet-encrypted at rest
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AppSettings(Base):
    """Key-value store for application settings."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded
