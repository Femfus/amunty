"""Re-export all models and Base so Alembic and init_db see everything."""

from amunty.models.base import Base
from amunty.models.conversation import Conversation
from amunty.models.message import Message
from amunty.models.settings import AppSettings, ModelConfig
from amunty.models.user import User
from amunty.models.odysseus_models import (
    Document,
    DocumentVersion,
    CrewMember,
    ScheduledTask,
    TaskRun,
    CalendarCal,
    CalendarEvent,
)

__all__ = [
    "Base",
    "Conversation",
    "Message",
    "ModelConfig",
    "AppSettings",
    "User",
    "Document",
    "DocumentVersion",
    "CrewMember",
    "ScheduledTask",
    "TaskRun",
    "CalendarCal",
    "CalendarEvent",
]
