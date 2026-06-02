"""Cookbook API — hardware detection, model catalog, model download management."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from amunty.deps import CurrentUser
from amunty.services.cookbook import (
    OllamaModelManager,
    detect_hardware,
    get_compatible_models,
    MODEL_CATALOG,
)

router = APIRouter()


class HardwareResponse(BaseModel):
    cpu_name: str
    cpu_cores: int
    cpu_threads: int
    ram_total_gb: float
    ram_available_gb: float
    accelerator: str
    gpu_name: str
    vram_total_gb: float
    vram_available_gb: float
    max_model_params_b: float
    tier: str


class CatalogModelOut(BaseModel):
    name: str
    display_name: str
    description: str
    parameter_count_b: float
    quantization: str
    disk_size_gb: float
    ram_required_gb: float
    min_tier: str
    category: str
    supports_tools: bool
    supports_vision: bool
    context_length: int
    recommended: bool
    tags: list[str]
    can_run: bool = False
    performance_note: str = ""
    installed: bool = False


class CatalogResponse(BaseModel):
    hardware: HardwareResponse
    models: list[CatalogModelOut]
    ollama_available: bool


class InstalledModelOut(BaseModel):
    name: str
    size_gb: float
    modified_at: str


class PullRequest(BaseModel):
    model_name: str


class DeleteRequest(BaseModel):
    model_name: str


@router.get("/hardware", response_model=HardwareResponse)
async def get_hardware(user: CurrentUser) -> HardwareResponse:
    """Detect and return the host's hardware profile."""
    profile = await detect_hardware()
    return HardwareResponse(**profile.to_dict())


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(user: CurrentUser) -> CatalogResponse:
    """Get the model catalog with hardware-matched compatibility info.

    Each model includes a `can_run` boolean and `performance_note` based
    on the detected hardware.
    """
    profile = await detect_hardware()
    compatible = get_compatible_models(profile)

    # Check if Ollama is available
    from amunty.config import settings

    ollama_url = settings.ollama_url or "http://localhost:11434"
    manager = OllamaModelManager(ollama_url)
    ollama_ok = await manager.is_available()

    # Mark installed models
    installed_names: set[str] = set()
    if ollama_ok:
        installed = await manager.list_installed()
        installed_names = {m["name"] for m in installed}

    for model in compatible:
        model["installed"] = model["name"] in installed_names

    return CatalogResponse(
        hardware=HardwareResponse(**profile.to_dict()),
        models=[CatalogModelOut(**m) for m in compatible],
        ollama_available=ollama_ok,
    )


@router.get("/installed", response_model=list[InstalledModelOut])
async def get_installed_models(user: CurrentUser) -> list[InstalledModelOut]:
    """List all models currently installed in Ollama."""
    from amunty.config import settings

    ollama_url = settings.ollama_url or "http://localhost:11434"
    manager = OllamaModelManager(ollama_url)

    if not await manager.is_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not reachable. Make sure it's running.",
        )

    installed = await manager.list_installed()
    return [InstalledModelOut(**m) for m in installed]


@router.post("/pull")
async def pull_model(body: PullRequest, user: CurrentUser) -> StreamingResponse:
    """Download a model from the Ollama registry.

    Returns a stream of progress events (SSE):
        data: {"status": "downloading ...", "percent": 45.2, ...}
        data: {"status": "success", "percent": 100}

    After download completes, the model is automatically registered with the
    gateway so it can be used immediately for conversations.
    """
    from amunty.config import settings

    ollama_url = settings.ollama_url or "http://localhost:11434"
    manager = OllamaModelManager(ollama_url)

    if not await manager.is_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not reachable. Make sure it's running.",
        )

    async def event_stream():
        pull_succeeded = False
        last_error = ""

        async for progress in manager.pull_model(body.model_name):
            data = progress.to_dict()
            yield f"data: {json.dumps(data)}\n\n"

            # Ollama sends status="success" when the pull finishes ok
            if progress.status == "success":
                pull_succeeded = True
            elif progress.status.startswith("error"):
                last_error = progress.status

        if not pull_succeeded:
            yield f'data: {json.dumps({"status": "error", "percent": 0, "error": last_error or "Pull failed"})}\n\n'
            return

        # Ensure the single "ollama" backend is registered in the gateway.
        # The OllamaBackend automatically lists ALL installed models via /api/tags,
        # so we don't need per-model backend entries.
        try:
            from amunty.services.model_gateway.registry import gateway

            if "ollama" not in gateway.backend_names:
                gateway.register_backend(
                    name="ollama",
                    backend_type="ollama",
                    base_url=ollama_url,
                )
        except Exception as exc:
            import logging
            logging.getLogger("amunty.cookbook").warning(
                "Ensure ollama backend after pull failed: %s", exc
            )

        yield f"data: {json.dumps({'status': 'complete', 'percent': 100})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/model")
async def delete_model(body: DeleteRequest, user: CurrentUser) -> dict:
    """Delete an installed model from Ollama."""
    from amunty.config import settings

    ollama_url = settings.ollama_url or "http://localhost:11434"
    manager = OllamaModelManager(ollama_url)

    success = await manager.delete_model(body.model_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete model.")

    return {"detail": f"Model '{body.model_name}' deleted."}
