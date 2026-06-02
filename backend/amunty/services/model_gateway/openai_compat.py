"""OpenAI-compatible model backend — works with OpenAI, OpenRouter, vLLM, llama.cpp server."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from amunty.services.model_gateway.base import (
    CompletionConfig,
    ModelBackend,
    ModelInfo,
    StreamChunk,
)

logger = logging.getLogger("amunty.gateway.openai_compat")


class OpenAICompatBackend:
    """Adapter for any OpenAI-compatible API (OpenAI, OpenRouter, vLLM, llama.cpp server)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        backend_name: str = "openai",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.backend_name = backend_name
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=120.0
        )

    async def list_models(self) -> list[ModelInfo]:
        """Fetch available models from /v1/models."""
        try:
            resp = await self._client.get("/v1/models")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning(
                "Failed to list models from %s: %s", self.base_url, exc
            )
            return []

        models: list[ModelInfo] = []
        for m in data.get("data", []):
            model_id = m.get("id", "")
            models.append(
                ModelInfo(
                    id=f"{self.backend_name}/{model_id}",
                    name=model_id,
                    backend=self.backend_name,
                    context_length=m.get("context_length", 4096),
                    supports_tools=True,  # Most OpenAI-compat APIs support function calling
                    supports_vision="vision" in model_id.lower()
                    or "4o" in model_id
                    or "gpt-4-turbo" in model_id,
                )
            )
        return models

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        config: CompletionConfig,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion using the OpenAI /v1/chat/completions endpoint."""
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if config.max_tokens is not None:
            payload["max_tokens"] = config.max_tokens
        if config.stop:
            payload["stop"] = config.stop
            
        # Tiny models (< 3B params) completely fail at tool calling and hallucinate the schemas
        # directly into the chat. Strip tools from the payload for these models.
        is_tiny = any(sz in model.lower() for sz in ["1b", "2b", "0.5b", "0.3b"])
        if config.tools and not is_tiny:
            payload["tools"] = config.tools

        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line == "data: [DONE]":
                        yield StreamChunk(delta="", finish_reason="stop")
                        break
                    if not line.startswith("data: "):
                        continue

                    json_str = line[6:]  # Remove "data: " prefix
                    try:
                        chunk = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish = choices[0].get("finish_reason")

                    # Handle tool calls
                    tool_calls_delta = delta.get("tool_calls")
                    if tool_calls_delta:
                        yield StreamChunk(
                            delta="",
                            tool_calls=[
                                {
                                    "id": tc.get("id", f"call_{tc.get('index', 0)}"),
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": tc.get("function", {}).get(
                                            "arguments", ""
                                        ),
                                    },
                                }
                                for tc in tool_calls_delta
                            ],
                        )
                        continue

                    content = delta.get("content", "")
                    yield StreamChunk(
                        delta=content or "",
                        finish_reason=finish,
                    )

        except httpx.HTTPError as exc:
            logger.error("OpenAI-compat streaming error: %s", exc)
            yield StreamChunk(
                delta=f"\n\n[Error communicating with {self.backend_name}: {exc}]",
                finish_reason="error",
            )

    async def health_check(self) -> bool:
        """Check if the API is reachable."""
        try:
            resp = await self._client.get("/v1/models")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
