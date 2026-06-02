"""Settings API — read and update app-wide settings."""

from __future__ import annotations

import json
import socket

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from amunty.deps import DB, CurrentUser
from amunty.models.settings import AppSettings

router = APIRouter()

# Default settings that are created if they don't exist
DEFAULT_SETTINGS: dict[str, str] = {
    "default_model": "",
    "system_prompt": "You are a helpful AI assistant running inside Amunty, a self-hosted workspace. Be concise, accurate, and helpful.",
    "theme": "dark",
    "memory_enabled": "true",
    # Permissions
    "allow_web_search": "false",
    "allow_file_read": "false",
    "allow_shell": "false",
    "allow_memory": "true",
    # Ollama
    "ollama_auto_discover": "true",
}

def get_local_ip() -> str:
    """Helper to get the machine's local network IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class SettingsResponse(BaseModel):
    settings: dict[str, str]


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.get("", response_model=SettingsResponse)
async def get_settings(db: DB, user: CurrentUser) -> SettingsResponse:
    """Get all application settings."""
    result = await db.execute(select(AppSettings))
    rows = result.scalars().all()
    current = {row.key: row.value for row in rows}

    # Fill in defaults for any missing keys
    for key, default in DEFAULT_SETTINGS.items():
        if key not in current:
            setting = AppSettings(key=key, value=default)
            db.add(setting)
            current[key] = default

    await db.flush()
    current["local_ip"] = get_local_ip()
    return SettingsResponse(settings=current)


@router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, db: DB, user: CurrentUser) -> SettingsResponse:
    """Bulk update application settings."""
    for key, value in body.settings.items():
        result = await db.execute(select(AppSettings).where(AppSettings.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(AppSettings(key=key, value=value))

    await db.flush()

    # Return all settings
    result = await db.execute(select(AppSettings))
    rows = result.scalars().all()
    current = {row.key: row.value for row in rows}
    current["local_ip"] = get_local_ip()
    return SettingsResponse(settings=current)
