"""Model gateway base types and protocol."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from pydantic import BaseModel


class ModelInfo(BaseModel):
    """Metadata about an available model."""

    id: str  # e.g., "ollama/llama3.3"
    name: str  # Display name
    backend: str  # "ollama", "openai", "vllm", "llamacpp"
    context_length: int = 4096
    supports_tools: bool = False
    supports_vision: bool = False


class StreamChunk(BaseModel):
    """A single token or event from a streaming completion."""

    delta: str = ""
    finish_reason: str | None = None
    tool_calls: list[dict] | None = None


class CompletionConfig(BaseModel):
    """Parameters for a chat completion request."""

    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    stop: list[str] | None = None
    tools: list[dict] | None = None  # OpenAI function-calling schema


@runtime_checkable
class ModelBackend(Protocol):
    """Protocol that every model backend must implement."""

    async def list_models(self) -> list[ModelInfo]: ...

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        config: CompletionConfig,
    ) -> AsyncIterator[StreamChunk]: ...

    async def health_check(self) -> bool: ...
