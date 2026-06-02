"""Model Gateway Registry — routes model_id to the correct backend."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from amunty.services.model_gateway.base import (
    CompletionConfig,
    ModelInfo,
    StreamChunk,
)
from amunty.services.model_gateway.ollama import OllamaBackend
from amunty.services.model_gateway.openai_compat import OpenAICompatBackend

logger = logging.getLogger("amunty.gateway.registry")

# Map of backend_type → class
BACKEND_CLASSES = {
    "ollama": OllamaBackend,
    "openai": OpenAICompatBackend,
    "vllm": OpenAICompatBackend,
    "llamacpp": OpenAICompatBackend,
}


class ModelGateway:
    """Routes model requests to the correct backend.

    Model IDs are namespaced: ``{backend_name}/{model_name}``.
    Example: ``ollama/llama3.3``, ``openai/gpt-4o``
    """

    def __init__(self) -> None:
        self._backends: dict[str, OllamaBackend | OpenAICompatBackend] = {}

    def register_backend(
        self,
        name: str,
        backend_type: str,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        """Register a model backend by name."""
        cls = BACKEND_CLASSES.get(backend_type)
        if cls is None:
            raise ValueError(f"Unknown backend type: {backend_type}")

        if backend_type == "ollama":
            self._backends[name] = OllamaBackend(base_url=base_url, backend_name=name)
        else:
            self._backends[name] = OpenAICompatBackend(
                base_url=base_url, api_key=api_key, backend_name=name
            )
        logger.info("Registered backend: %s (%s) at %s", name, backend_type, base_url)

    def unregister_backend(self, name: str) -> None:
        """Remove a backend by name."""
        self._backends.pop(name, None)
        logger.info("Unregistered backend: %s", name)

    def _resolve(self, model_id: str) -> tuple[OllamaBackend | OpenAICompatBackend, str]:
        """Parse model_id into (backend, model_name).

        E.g. ``"ollama/llama3.3"`` → ``(OllamaBackend, "llama3.3")``
        """
        if "/" not in model_id:
            # Fallback for old un-namespaced model IDs
            model_name = model_id
            if model_id.startswith("gpt-") or model_id.startswith("claude-") or model_id.startswith("gemini-"):
                backend_name = "openai" if "openai" in self._backends else list(self._backends.keys())[0] if self._backends else "openai"
            else:
                backend_name = "ollama" if "ollama" in self._backends else list(self._backends.keys())[0] if self._backends else "ollama"
        else:
            backend_name, model_name = model_id.split("/", 1)

        backend = self._backends.get(backend_name)
        if backend is None:
            available = ", ".join(self._backends.keys()) or "(none)"
            raise ValueError(
                f"Backend '{backend_name}' not found. Available: {available}"
            )

        return backend, model_name

    async def list_all_models(self) -> list[ModelInfo]:
        """List models from all registered backends."""
        all_models: list[ModelInfo] = []
        for name, backend in self._backends.items():
            try:
                models = await backend.list_models()
                all_models.extend(models)
            except Exception as exc:
                logger.warning("Failed to list models from %s: %s", name, exc)
        return all_models

    async def complete(
        self,
        model_id: str,
        messages: list[dict],
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion from the appropriate backend."""
        backend, model_name = self._resolve(model_id)
        cfg = config or CompletionConfig()

        async for chunk in backend.chat_completion(messages, model_name, cfg):
            yield chunk

    async def health_check(self, backend_name: str) -> bool:
        """Check if a specific backend is healthy."""
        backend = self._backends.get(backend_name)
        if backend is None:
            return False
        return await backend.health_check()

    @property
    def backend_names(self) -> list[str]:
        """List all registered backend names."""
        return list(self._backends.keys())


# Singleton gateway instance
gateway = ModelGateway()
