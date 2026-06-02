"""Cookbook — model library, hardware detection, and Ollama model management.

Provides:
- Hardware profiling (RAM, VRAM, CPU)
- Curated model catalog with hardware-matched recommendations
- Pull/download models via Ollama's API
- Real-time download progress tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator

import httpx

logger = logging.getLogger("amunty.cookbook")


# ---------------------------------------------------------------------------
# Hardware profiling
# ---------------------------------------------------------------------------


class AcceleratorType(str, Enum):
    NONE = "none"
    NVIDIA = "nvidia"
    AMD = "amd"
    APPLE_SILICON = "apple_silicon"
    INTEL_ARC = "intel_arc"


@dataclass
class HardwareProfile:
    """Detected hardware capabilities of the host machine."""

    cpu_name: str = "Unknown"
    cpu_cores: int = 1
    cpu_threads: int = 1
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0

    # GPU
    accelerator: AcceleratorType = AcceleratorType.NONE
    gpu_name: str = ""
    vram_total_gb: float = 0.0
    vram_available_gb: float = 0.0

    # Derived
    max_model_params_b: float = 0.0  # Estimated max model size in billions of params
    tier: str = "unknown"  # "low", "mid", "high", "ultra"

    def to_dict(self) -> dict:
        return {
            "cpu_name": self.cpu_name,
            "cpu_cores": self.cpu_cores,
            "cpu_threads": self.cpu_threads,
            "ram_total_gb": round(self.ram_total_gb, 1),
            "ram_available_gb": round(self.ram_available_gb, 1),
            "accelerator": self.accelerator.value,
            "gpu_name": self.gpu_name,
            "vram_total_gb": round(self.vram_total_gb, 1),
            "vram_available_gb": round(self.vram_available_gb, 1),
            "max_model_params_b": round(self.max_model_params_b, 1),
            "tier": self.tier,
        }


async def detect_hardware() -> HardwareProfile:
    """Detect the host's CPU, RAM, and GPU capabilities.

    Works cross-platform (Windows, macOS, Linux). GPU detection uses
    nvidia-smi for NVIDIA, and falls back to psutil for memory info.
    """
    profile = HardwareProfile()

    # --- CPU ---
    profile.cpu_name = platform.processor() or platform.machine()
    try:
        import os

        profile.cpu_cores = os.cpu_count() or 1
        profile.cpu_threads = profile.cpu_cores  # Approximation
    except Exception:
        pass

    # --- RAM ---
    try:
        import shutil

        # Cross-platform: use shutil.disk_usage as a fallback indicator,
        # but prefer psutil if available
        try:
            import psutil  # type: ignore[import-untyped]

            mem = psutil.virtual_memory()
            profile.ram_total_gb = mem.total / (1024**3)
            profile.ram_available_gb = mem.available / (1024**3)
        except ImportError:
            # Fallback: read /proc/meminfo on Linux
            if platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            profile.ram_total_gb = kb / (1024**2)
                        elif line.startswith("MemAvailable:"):
                            kb = int(line.split()[1])
                            profile.ram_available_gb = kb / (1024**2)
    except Exception as exc:
        logger.warning("Failed to detect RAM: %s", exc)

    # --- GPU: NVIDIA via nvidia-smi ---
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0 and stdout:
            line = stdout.decode().strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                profile.accelerator = AcceleratorType.NVIDIA
                profile.gpu_name = parts[0]
                profile.vram_total_gb = float(parts[1]) / 1024
                profile.vram_available_gb = float(parts[2]) / 1024
    except (FileNotFoundError, asyncio.TimeoutError):
        pass
    except Exception as exc:
        logger.debug("nvidia-smi detection failed: %s", exc)

    # --- GPU: Apple Silicon ---
    if platform.system() == "Darwin" and "arm" in platform.machine().lower():
        profile.accelerator = AcceleratorType.APPLE_SILICON
        profile.gpu_name = f"Apple {platform.machine()}"
        # On Apple Silicon, unified memory is shared between CPU and GPU
        # Ollama can use ~75% of total RAM for the model
        profile.vram_total_gb = profile.ram_total_gb * 0.75
        profile.vram_available_gb = profile.ram_available_gb * 0.75

    # --- Estimate max model size ---
    # Rule of thumb: ~0.5 GB per billion params (Q4 quantization)
    # GPU inference needs model to fit in VRAM
    # CPU inference needs model to fit in RAM (slower but works)
    if profile.vram_total_gb > 0:
        profile.max_model_params_b = profile.vram_total_gb / 0.5
    else:
        # CPU-only: can use most of RAM but leave ~4 GB for OS
        usable_ram = max(0, profile.ram_total_gb - 4.0)
        profile.max_model_params_b = usable_ram / 0.5

    # --- Assign tier ---
    if profile.max_model_params_b >= 60:
        profile.tier = "ultra"     # Can run 70B+ models
    elif profile.max_model_params_b >= 25:
        profile.tier = "high"      # Can run 27B-32B models
    elif profile.max_model_params_b >= 12:
        profile.tier = "mid"       # Can run 7B-14B models
    elif profile.max_model_params_b >= 3:
        profile.tier = "low"       # Can run 1B-3B models
    else:
        profile.tier = "minimal"   # Barely anything

    return profile


# ---------------------------------------------------------------------------
# Model catalog — curated list of recommended models for Ollama
# ---------------------------------------------------------------------------


@dataclass
class CatalogModel:
    """A model in the curated catalog."""

    name: str                      # Ollama model name, e.g., "llama3.2:3b"
    display_name: str              # Human-friendly name
    description: str
    parameter_count_b: float       # Billions of parameters
    quantization: str              # e.g., "Q4_K_M", "FP16"
    disk_size_gb: float            # Approximate download size
    ram_required_gb: float         # Minimum RAM/VRAM to run
    min_tier: str                  # Minimum hardware tier
    category: str                  # "general", "coding", "vision", "reasoning", "small"
    supports_tools: bool = False
    supports_vision: bool = False
    context_length: int = 8192
    recommended: bool = False      # Show as a top pick for the tier
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "parameter_count_b": self.parameter_count_b,
            "quantization": self.quantization,
            "disk_size_gb": self.disk_size_gb,
            "ram_required_gb": self.ram_required_gb,
            "min_tier": self.min_tier,
            "category": self.category,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "context_length": self.context_length,
            "recommended": self.recommended,
            "tags": self.tags,
        }


# The catalog — updated periodically as new models release
MODEL_CATALOG: list[CatalogModel] = [
    # ── Small / Low-tier ──
    CatalogModel(
        name="llama3.2:1b",
        display_name="Llama 3.2 1B",
        description="Meta's smallest model. Fast, lightweight, good for simple tasks and resource-constrained systems.",
        parameter_count_b=1.0,
        quantization="Q4_K_M",
        disk_size_gb=0.7,
        ram_required_gb=1.5,
        min_tier="minimal",
        category="small",
        supports_tools=True,
        context_length=131072,
        recommended=True,
        tags=["fast", "lightweight", "meta"],
    ),
    CatalogModel(
        name="llama3.2:3b",
        display_name="Llama 3.2 3B",
        description="Great balance of speed and quality for everyday use. Excellent for chatting and simple tasks.",
        parameter_count_b=3.0,
        quantization="Q4_K_M",
        disk_size_gb=2.0,
        ram_required_gb=3.5,
        min_tier="low",
        category="general",
        supports_tools=True,
        context_length=131072,
        recommended=True,
        tags=["balanced", "meta"],
    ),
    CatalogModel(
        name="phi4-mini",
        display_name="Phi-4 Mini",
        description="Microsoft's small but powerful model. Punches above its weight for reasoning and coding.",
        parameter_count_b=3.8,
        quantization="Q4_K_M",
        disk_size_gb=2.5,
        ram_required_gb=4.0,
        min_tier="low",
        category="coding",
        supports_tools=True,
        context_length=16384,
        recommended=True,
        tags=["coding", "reasoning", "microsoft"],
    ),
    CatalogModel(
        name="qwen3:4b",
        display_name="Qwen 3 4B",
        description="Alibaba's compact model with strong multilingual support and tool calling.",
        parameter_count_b=4.0,
        quantization="Q4_K_M",
        disk_size_gb=2.6,
        ram_required_gb=4.5,
        min_tier="low",
        category="general",
        supports_tools=True,
        context_length=32768,
        tags=["multilingual", "alibaba"],
    ),

    # ── Mid-tier (7B-14B) ──
    CatalogModel(
        name="llama3.1:8b",
        display_name="Llama 3.1 8B",
        description="Meta's flagship small model. Excellent all-around performance with tool calling support.",
        parameter_count_b=8.0,
        quantization="Q4_K_M",
        disk_size_gb=4.7,
        ram_required_gb=6.0,
        min_tier="mid",
        category="general",
        supports_tools=True,
        context_length=131072,
        recommended=True,
        tags=["flagship", "meta", "tool-calling"],
    ),
    CatalogModel(
        name="gemma3:12b",
        display_name="Gemma 3 12B",
        description="Google's 12B model with vision capabilities. Strong at both text and image understanding.",
        parameter_count_b=12.0,
        quantization="Q4_K_M",
        disk_size_gb=7.6,
        ram_required_gb=10.0,
        min_tier="mid",
        category="vision",
        supports_tools=True,
        supports_vision=True,
        context_length=131072,
        recommended=True,
        tags=["vision", "multimodal", "google"],
    ),
    CatalogModel(
        name="qwen3:8b",
        display_name="Qwen 3 8B",
        description="Alibaba's 8B model with hybrid thinking mode and strong tool-use capabilities.",
        parameter_count_b=8.0,
        quantization="Q4_K_M",
        disk_size_gb=5.2,
        ram_required_gb=6.5,
        min_tier="mid",
        category="general",
        supports_tools=True,
        context_length=32768,
        tags=["thinking", "alibaba", "tool-calling"],
    ),
    CatalogModel(
        name="deepseek-coder-v2:16b",
        display_name="DeepSeek Coder V2 16B",
        description="Specialist coding model. Excellent at code generation, debugging, and explanation.",
        parameter_count_b=16.0,
        quantization="Q4_K_M",
        disk_size_gb=9.0,
        ram_required_gb=12.0,
        min_tier="mid",
        category="coding",
        supports_tools=True,
        context_length=131072,
        tags=["coding", "deepseek"],
    ),

    # ── High-tier (27B-32B) ──
    CatalogModel(
        name="gemma3:27b",
        display_name="Gemma 3 27B",
        description="Google's premium model with vision. Near-frontier quality for text and image tasks.",
        parameter_count_b=27.0,
        quantization="Q4_K_M",
        disk_size_gb=17.0,
        ram_required_gb=20.0,
        min_tier="high",
        category="vision",
        supports_tools=True,
        supports_vision=True,
        context_length=131072,
        recommended=True,
        tags=["vision", "premium", "google"],
    ),
    CatalogModel(
        name="qwen3:32b",
        display_name="Qwen 3 32B",
        description="Alibaba's 32B powerhouse with hybrid thinking. Rivals commercial APIs for complex reasoning.",
        parameter_count_b=32.0,
        quantization="Q4_K_M",
        disk_size_gb=20.0,
        ram_required_gb=24.0,
        min_tier="high",
        category="reasoning",
        supports_tools=True,
        context_length=32768,
        recommended=True,
        tags=["reasoning", "thinking", "alibaba"],
    ),
    CatalogModel(
        name="command-r:35b",
        display_name="Command R 35B",
        description="Cohere's RAG-optimized model. Best-in-class for retrieval, tool use, and structured outputs.",
        parameter_count_b=35.0,
        quantization="Q4_K_M",
        disk_size_gb=20.0,
        ram_required_gb=24.0,
        min_tier="high",
        category="general",
        supports_tools=True,
        context_length=131072,
        tags=["RAG", "tool-calling", "cohere"],
    ),

    # ── Ultra-tier (70B+) ──
    CatalogModel(
        name="llama3.3:70b",
        display_name="Llama 3.3 70B",
        description="Meta's largest open model. Near-GPT-4 quality. Requires serious hardware.",
        parameter_count_b=70.0,
        quantization="Q4_K_M",
        disk_size_gb=43.0,
        ram_required_gb=48.0,
        min_tier="ultra",
        category="general",
        supports_tools=True,
        context_length=131072,
        recommended=True,
        tags=["frontier", "meta", "premium"],
    ),
    CatalogModel(
        name="qwen3:72b",
        display_name="Qwen 3 72B",
        description="Alibaba's largest model with hybrid thinking. Competes with proprietary frontier models.",
        parameter_count_b=72.0,
        quantization="Q4_K_M",
        disk_size_gb=44.0,
        ram_required_gb=50.0,
        min_tier="ultra",
        category="reasoning",
        supports_tools=True,
        context_length=32768,
        tags=["frontier", "thinking", "alibaba"],
    ),
    CatalogModel(
        name="deepseek-r1:70b",
        display_name="DeepSeek R1 70B",
        description="DeepSeek's reasoning model with chain-of-thought. Exceptional for math and logic.",
        parameter_count_b=70.0,
        quantization="Q4_K_M",
        disk_size_gb=43.0,
        ram_required_gb=48.0,
        min_tier="ultra",
        category="reasoning",
        supports_tools=False,
        context_length=65536,
        tags=["reasoning", "math", "deepseek"],
    ),
]


def get_compatible_models(profile: HardwareProfile) -> list[dict]:
    """Filter and rank catalog models that can run on the detected hardware.

    Returns models sorted by: recommended first, then by compatibility score.
    """
    tier_order = {"minimal": 0, "low": 1, "mid": 2, "high": 3, "ultra": 4}
    user_tier = tier_order.get(profile.tier, 0)

    results: list[dict] = []
    for model in MODEL_CATALOG:
        model_tier = tier_order.get(model.min_tier, 0)
        can_run = model_tier <= user_tier

        # More granular: check RAM/VRAM
        if profile.vram_total_gb > 0:
            fits_memory = model.ram_required_gb <= profile.vram_total_gb
        else:
            fits_memory = model.ram_required_gb <= profile.ram_total_gb

        entry = model.to_dict()
        entry["can_run"] = can_run and fits_memory
        entry["performance_note"] = _performance_note(model, profile)

        results.append(entry)

    # Sort: recommended & runnable first, then by param count ascending
    results.sort(key=lambda m: (
        not m["can_run"],
        not m.get("recommended", False),
        m["parameter_count_b"],
    ))

    return results


def _performance_note(model: CatalogModel, profile: HardwareProfile) -> str:
    """Generate a human-readable performance estimate."""
    if profile.vram_total_gb >= model.ram_required_gb:
        headroom = profile.vram_total_gb - model.ram_required_gb
        if headroom > 5:
            return "⚡ Excellent — runs fast with room to spare"
        elif headroom > 1:
            return "✅ Good — fits comfortably in VRAM"
        else:
            return "⚠️ Tight — will run but at VRAM limit"
    elif profile.ram_total_gb >= model.ram_required_gb:
        if profile.accelerator == AcceleratorType.APPLE_SILICON:
            return "✅ Good — Apple Silicon unified memory"
        return "🐢 CPU-only — functional but slow (~1-5 tokens/sec)"
    else:
        return "❌ Insufficient memory — model may not load"


# ---------------------------------------------------------------------------
# Ollama model management — pull, delete, list
# ---------------------------------------------------------------------------


@dataclass
class PullProgress:
    """Progress event during a model pull."""

    status: str               # "pulling manifest", "downloading ...", "verifying", "done"
    total_bytes: int = 0
    completed_bytes: int = 0
    percent: float = 0.0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "total_bytes": self.total_bytes,
            "completed_bytes": self.completed_bytes,
            "percent": round(self.percent, 1),
        }


class OllamaModelManager:
    """Manages model downloads and lifecycle via Ollama's API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=600.0)

    async def list_installed(self) -> list[dict]:
        """List all models currently installed in Ollama."""
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size_gb": round(m.get("size", 0) / (1024**3), 1),
                    "modified_at": m.get("modified_at", ""),
                    "details": m.get("details", {}),
                }
                for m in models
            ]
        except httpx.HTTPError as exc:
            logger.warning("Failed to list Ollama models: %s", exc)
            return []

    async def pull_model(self, model_name: str) -> AsyncIterator[PullProgress]:
        """Pull (download) a model from the Ollama registry.

        Yields PullProgress events as the download progresses.
        """
        try:
            async with self._client.stream(
                "POST",
                "/api/pull",
                json={"name": model_name, "stream": True},
                timeout=None,  # Downloads can take a very long time
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    status = data.get("status", "")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    percent = (completed / total * 100) if total > 0 else 0

                    yield PullProgress(
                        status=status,
                        total_bytes=total,
                        completed_bytes=completed,
                        percent=percent,
                    )

        except httpx.HTTPError as exc:
            logger.error("Failed to pull model %s: %s", model_name, exc)
            yield PullProgress(status=f"error: {exc}")

    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            resp = await self._client.delete("/api/delete", json={"name": model_name})
            return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.error("Failed to delete model %s: %s", model_name, exc)
            return False

    async def model_info(self, model_name: str) -> dict | None:
        """Get detailed info about an installed model."""
        try:
            resp = await self._client.post("/api/show", json={"name": model_name})
            if resp.status_code == 200:
                return resp.json()
            return None
        except httpx.HTTPError:
            return None

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
