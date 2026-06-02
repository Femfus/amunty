"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from amunty.config import settings
from amunty.database import init_db
from amunty.security import ensure_first_run

logger = logging.getLogger("amunty")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    # Ensure data directories exist
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database (run migrations)
    await init_db()

    # First-run: create admin user, generate password if needed
    await ensure_first_run()

    # Register model backends from database
    await _bootstrap_backends()

    # Register system tools (PC assistant capabilities)
    import amunty.services.tools  # noqa: F401 — triggers auto-registration

    # Load skills system
    from amunty.services.skills import skills_manager
    skills_manager.load()

    # Load MCP servers
    from amunty.services.mcp_client import mcp_manager
    await mcp_manager.initialize()

    logger.info("Amunty v%s started on port %d", "0.1.0", settings.app_port)
    logger.info("Registered %d system tools", len(amunty.services.tools.tool_registry))
    logger.info("Loaded %d skills", len(skills_manager))
    yield
    await mcp_manager.shutdown()
    logger.info("Amunty shutting down.")


async def _bootstrap_backends() -> None:
    """Load all enabled model backends from the database and register them."""
    from amunty.database import async_session
    from amunty.models.settings import ModelConfig
    from amunty.security import decrypt_value
    from amunty.services.model_gateway.registry import gateway

    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(ModelConfig).where(ModelConfig.is_enabled == True)  # noqa: E712
        )
        configs = result.scalars().all()

        for cfg in configs:
            # Skip stale per-model Ollama entries (e.g. "ollama/llama3.2:1b")
            # — only the single "ollama" backend should be registered.
            if cfg.backend_type == "ollama" and cfg.name != "ollama":
                continue
            try:
                api_key = decrypt_value(cfg.api_key) if cfg.api_key else None
                gateway.register_backend(
                    name=cfg.name,
                    backend_type=cfg.backend_type,
                    base_url=cfg.base_url,
                    api_key=api_key,
                )
            except Exception as exc:
                logger.warning("Failed to register backend '%s': %s", cfg.name, exc)

    # Auto-register Ollama if URL is set and not already registered
    ollama_url = settings.ollama_url or "http://localhost:11434"
    if "ollama" not in gateway.backend_names:
        gateway.register_backend(
            name="ollama",
            backend_type="ollama",
            base_url=ollama_url,
        )

    # Auto-register OpenAI if OPENAI_API_KEY exists in env
    import os
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and "openai" not in gateway.backend_names:
        gateway.register_backend(
            name="openai",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            api_key=openai_key,
        )


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # --- Middleware ---
    allowed_origins = [
        f"http://localhost:{settings.app_port}",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        f"http://127.0.0.1:{settings.app_port}",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- API routes ---
    from amunty.api import router as api_router
    from amunty.api.skills import router as skills_router

    app.include_router(api_router, prefix="/api")
    app.include_router(skills_router)  # already has /api/skills prefix

    # --- Static files (built frontend) ---
    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
