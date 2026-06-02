"""Models API — list available models, manage backends."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from amunty.deps import DB, CurrentUser
from amunty.models.settings import ModelConfig
from amunty.security import decrypt_value, encrypt_value
from amunty.services.model_gateway.registry import gateway

router = APIRouter()


class BackendCreate(BaseModel):
    backend_type: str  # "ollama", "openai", "vllm", "llamacpp"
    name: str
    base_url: str
    api_key: str | None = None


class BackendUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_enabled: bool | None = None


class BackendOut(BaseModel):
    id: str
    backend_type: str
    name: str
    base_url: str
    has_api_key: bool
    is_enabled: bool
    created_at: str

    model_config = {"from_attributes": True}


class ModelOut(BaseModel):
    id: str
    name: str
    backend: str
    context_length: int
    supports_tools: bool
    supports_vision: bool


class HealthCheckResult(BaseModel):
    healthy: bool


@router.get("", response_model=list[ModelOut])
async def list_models(user: CurrentUser) -> list[ModelOut]:
    """List all available models from all registered backends."""
    models = await gateway.list_all_models()
    return [
        ModelOut(
            id=m.id,
            name=m.name,
            backend=m.backend,
            context_length=m.context_length,
            supports_tools=m.supports_tools,
            supports_vision=m.supports_vision,
        )
        for m in models
    ]


@router.get("/backends", response_model=list[BackendOut])
async def list_backends(db: DB, user: CurrentUser) -> list[BackendOut]:
    """List all configured model backends."""
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.created_at))
    rows = result.scalars().all()
    return [
        BackendOut(
            id=r.id,
            backend_type=r.backend_type,
            name=r.name,
            base_url=r.base_url,
            has_api_key=r.api_key is not None,
            is_enabled=r.is_enabled,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/backends", response_model=BackendOut, status_code=201)
async def add_backend(body: BackendCreate, db: DB, user: CurrentUser) -> BackendOut:
    """Add a new model backend and register it with the gateway."""
    if body.backend_type not in ("ollama", "openai", "vllm", "llamacpp"):
        raise HTTPException(status_code=400, detail=f"Unknown backend type: {body.backend_type}")

    config = ModelConfig(
        id=str(uuid.uuid4()),
        backend_type=body.backend_type,
        name=body.name,
        base_url=body.base_url,
        api_key=encrypt_value(body.api_key) if body.api_key else None,
        is_enabled=True,
        created_at=datetime.now(UTC),
    )
    db.add(config)
    await db.flush()

    # Register with the live gateway
    gateway.register_backend(
        name=body.name,
        backend_type=body.backend_type,
        base_url=body.base_url,
        api_key=body.api_key,
    )

    return BackendOut(
        id=config.id,
        backend_type=config.backend_type,
        name=config.name,
        base_url=config.base_url,
        has_api_key=config.api_key is not None,
        is_enabled=config.is_enabled,
        created_at=config.created_at.isoformat(),
    )


@router.put("/backends/{backend_id}", response_model=BackendOut)
async def update_backend(
    backend_id: str, body: BackendUpdate, db: DB, user: CurrentUser
) -> BackendOut:
    """Update a model backend configuration."""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == backend_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Backend not found.")

    old_name = config.name

    if body.name is not None:
        config.name = body.name
    if body.base_url is not None:
        config.base_url = body.base_url
    if body.api_key is not None:
        config.api_key = encrypt_value(body.api_key)
    if body.is_enabled is not None:
        config.is_enabled = body.is_enabled

    await db.flush()

    # Re-register with gateway
    gateway.unregister_backend(old_name)
    if config.is_enabled:
        api_key = decrypt_value(config.api_key) if config.api_key else None
        gateway.register_backend(
            name=config.name,
            backend_type=config.backend_type,
            base_url=config.base_url,
            api_key=api_key,
        )

    return BackendOut(
        id=config.id,
        backend_type=config.backend_type,
        name=config.name,
        base_url=config.base_url,
        has_api_key=config.api_key is not None,
        is_enabled=config.is_enabled,
        created_at=config.created_at.isoformat(),
    )


@router.delete("/backends/{backend_id}", status_code=204)
async def delete_backend(backend_id: str, db: DB, user: CurrentUser) -> None:
    """Remove a model backend."""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == backend_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Backend not found.")

    gateway.unregister_backend(config.name)
    await db.delete(config)
    await db.flush()


@router.post("/backends/{backend_id}/test", response_model=HealthCheckResult)
async def test_backend(backend_id: str, db: DB, user: CurrentUser) -> HealthCheckResult:
    """Test connectivity to a model backend."""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == backend_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Backend not found.")

    healthy = await gateway.health_check(config.name)
    return HealthCheckResult(healthy=healthy)


class AutoDiscoverResult(BaseModel):
    discovered: int
    registered: list[str]


@router.post("/auto-discover", response_model=AutoDiscoverResult)
async def auto_discover_ollama(db: DB, user: CurrentUser) -> AutoDiscoverResult:
    """Ensure the single Ollama backend is registered and report installed models.

    Ollama uses a single backend entry named ``"ollama"`` — the OllamaBackend
    class queries ``/api/tags`` automatically to list all installed models.
    We do NOT need per-model backend entries.
    """
    from amunty.config import settings as app_settings
    from amunty.services.cookbook import OllamaModelManager

    ollama_url = app_settings.ollama_url or "http://localhost:11434"
    manager = OllamaModelManager(ollama_url)

    if not await manager.is_available():
        return AutoDiscoverResult(discovered=0, registered=[])

    # Ensure the single "ollama" backend is registered
    if "ollama" not in gateway.backend_names:
        gateway.register_backend(
            name="ollama",
            backend_type="ollama",
            base_url=ollama_url,
        )

        # Persist to DB so it survives restarts
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.name == "ollama")
        )
        if result.scalar_one_or_none() is None:
            config = ModelConfig(
                id=str(uuid.uuid4()),
                backend_type="ollama",
                name="ollama",
                base_url=ollama_url,
                api_key=None,
                is_enabled=True,
                created_at=datetime.now(UTC),
            )
            db.add(config)
            await db.flush()

    installed = await manager.list_installed()
    model_names = [m["name"] for m in installed]
    return AutoDiscoverResult(discovered=len(installed), registered=model_names)
