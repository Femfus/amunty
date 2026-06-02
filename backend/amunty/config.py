"""Application configuration loaded from environment variables."""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


def _load_or_generate_secret(filepath: Path, length: int = 48) -> str:
    """Load a secret from a file, or generate + persist a new one.

    This ensures JWT secrets survive process restarts so existing
    tokens remain valid.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if filepath.exists():
        return filepath.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(length)
    filepath.write_text(secret, encoding="utf-8")
    return secret


class Settings(BaseSettings):
    """All configuration for the Amunty backend.

    Values are read from environment variables (case-insensitive) or from a
    ``.env`` file when running outside Docker.
    """

    # --- Core ---
    app_name: str = "Amunty"
    app_port: int = 7000
    debug: bool = False

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///data/amunty.db"

    # --- ChromaDB ---
    chromadb_url: str = "http://chromadb:8000"

    # --- Auth ---
    auth_enabled: bool = False
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    amunty_admin_password: str | None = None  # If None, auto-generated on first boot

    # --- Encryption ---
    # Used to encrypt API keys stored in the database.
    # Auto-generated on first run, persisted to data/encryption.key
    encryption_key: str | None = None

    # --- Paths ---
    data_dir: Path = Path("data")
    workspace_dir: Path = Path("data/workspace")

    # --- External services ---
    searxng_url: str = "http://searxng:8080"
    ollama_url: str | None = None  # e.g., "http://host.docker.internal:11434"

    # --- Embedding ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # --- MCP Servers ---
    # List of command strings to run standard MCP servers over stdio
    # Example: ["npx -y @modelcontextprotocol/server-sqlite --db-path my.db"]
    mcp_servers: list[str] = []

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton — import this everywhere
settings = Settings()

# Ensure jwt_secret is persisted across restarts
if not settings.jwt_secret:
    settings.jwt_secret = _load_or_generate_secret(settings.data_dir / "jwt.key")
