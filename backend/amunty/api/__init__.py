"""API router — aggregates all route modules."""

from __future__ import annotations

from fastapi import APIRouter

from amunty.api.auth import router as auth_router
from amunty.api.chat import router as chat_router
from amunty.api.cookbook import router as cookbook_router
from amunty.api.conversations import router as conversations_router
from amunty.api.memory import router as memory_router
from amunty.api.models import router as models_router
from amunty.api.settings import router as settings_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(cookbook_router, prefix="/cookbook", tags=["cookbook"])
router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
router.include_router(models_router, prefix="/models", tags=["models"])
router.include_router(memory_router, prefix="/memory", tags=["memory"])
router.include_router(settings_router, prefix="/settings", tags=["settings"])
