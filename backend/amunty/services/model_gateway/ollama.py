"""Ollama model backend — talks to Ollama's /api/chat endpoint."""

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

logger = logging.getLogger("amunty.gateway.ollama")


def _clean_messages_for_ollama(messages: list[dict]) -> list[dict]:
    """Clean messages for Ollama — remove tool-related entries and format images."""
    cleaned = []
    for msg in messages:
        role = msg.get("role", "")

        # Skip tool result messages entirely
        if role == "tool":
            continue

        cleaned_msg = {k: v for k, v in msg.items() if k != "tool_calls"}

        content = cleaned_msg.get("content", "")
        images = []
        
        # Handle Multimodal Vision format from chat_engine
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:image"):
                        try:
                            b64 = url.split("base64,")[1]
                            images.append(b64)
                        except IndexError:
                            pass
            cleaned_msg["content"] = "\n".join(text_parts).strip()
            if images:
                cleaned_msg["images"] = images

        # Strip tool_calls JSON representations from assistant messages
        if role == "assistant":
            c_str = cleaned_msg.get("content", "")
            if isinstance(c_str, str) and c_str.strip().startswith("{") and '"name"' in c_str:
                cleaned_msg["content"] = "(used a system tool)"

        cleaned.append(cleaned_msg)

    return cleaned

class OllamaBackend:
    """Adapter for Ollama's native API."""

    def __init__(self, base_url: str, backend_name: str = "ollama") -> None:
        self.base_url = base_url.rstrip("/")
        self.backend_name = backend_name
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def list_models(self) -> list[ModelInfo]:
        """Fetch available models from Ollama."""
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to list Ollama models at %s: %s", self.base_url, exc)
            return []

        models: list[ModelInfo] = []
        for m in data.get("models", []):
            name = m.get("name", "")
            details = m.get("details", {})
            # Determine context length from model details if available
            ctx = 4096
            params = details.get("parameter_size", "")
            # Heuristic: larger models often have larger context
            if "128k" in name.lower() or "128k" in str(m):
                ctx = 131072
            elif "32k" in name.lower():
                ctx = 32768

            models.append(
                ModelInfo(
                    id=f"{self.backend_name}/{name}",
                    name=name,
                    backend=self.backend_name,
                    context_length=ctx,
                    supports_tools="tools" in str(details.get("families", [])).lower()
                    or any(
                        kw in name.lower()
                        for kw in ["llama3", "qwen", "mistral", "gemma", "command-r"]
                    ),
                    supports_vision=any(
                        kw in name.lower() for kw in ["llava", "vision", "minicpm"]
                    ),
                )
            )
        return models

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        config: CompletionConfig,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion from Ollama."""
        # Clean messages: remove tool-related messages that might confuse Ollama
        clean_msgs = _clean_messages_for_ollama(messages)

        payload: dict = {
            "model": model,
            "messages": clean_msgs,
            "stream": True,
            "keep_alive": "1h",  # Optimization: Keep model and KV cache in memory for 1 hour for instant replies
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_ctx": 8192,  # Optimization: Large context window prevents KV cache dumping/resizing during long chats
            },
        }
        if config.max_tokens is not None:
            payload["options"]["num_predict"] = config.max_tokens
        if config.stop:
            payload["options"]["stop"] = config.stop

        # Tiny models (< 3B params) completely fail at tool calling and hallucinate the schemas
        # directly into the chat. Strip tools from the payload for these models.
        is_tiny = any(sz in model.lower() for sz in ["1b", "2b", "0.5b", "0.3b"])
        if config.tools and not is_tiny:
            payload["tools"] = config.tools

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code == 400:
                    # Read error body for debugging
                    body = await resp.aread()
                    error_text = body.decode("utf-8", errors="replace")
                    logger.warning("Ollama 400 error (with tools): %s", error_text[:500])

                    # Retry WITHOUT tools — model may not support them
                    if "tools" in payload:
                        logger.info("Retrying without tools...")
                        payload.pop("tools", None)
                        async for chunk in self._stream_payload(payload):
                            yield chunk
                        return
                    else:
                        yield StreamChunk(
                            delta=f"\n\n[Ollama error: {error_text[:200]}]",
                            finish_reason="error",
                        )
                        return

                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})

                    # Handle tool calls
                    tool_calls = msg.get("tool_calls")
                    if tool_calls:
                        yield StreamChunk(
                            delta="",
                            tool_calls=[
                                {
                                    "id": f"call_{i}",
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": json.dumps(
                                            tc["function"].get("arguments", {})
                                        ),
                                    },
                                }
                                for i, tc in enumerate(tool_calls)
                            ],
                        )
                        continue

                    content = msg.get("content", "")
                    done = chunk.get("done", False)

                    yield StreamChunk(
                        delta=content,
                        finish_reason="stop" if done and content == "" else None,
                    )

                    if done:
                        break
        except httpx.HTTPError as exc:
            logger.error("Ollama streaming error: %s", exc)
            yield StreamChunk(delta=f"\n\n[Error communicating with Ollama: {exc}]", finish_reason="error")

    async def _stream_payload(self, payload: dict) -> AsyncIterator[StreamChunk]:
        """Stream a payload without tool support (fallback)."""
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    done = chunk.get("done", False)

                    yield StreamChunk(
                        delta=content,
                        finish_reason="stop" if done and content == "" else None,
                    )
                    if done:
                        break
        except httpx.HTTPError as exc:
            logger.error("Ollama fallback error: %s", exc)
            yield StreamChunk(delta=f"\n\n[Ollama error: {exc}]", finish_reason="error")

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
