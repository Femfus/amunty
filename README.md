# Amunty

A self-hosted, local-first AI workspace — think ChatGPT, but running on your hardware with your data.

## Quick Start

```bash
git clone https://github.com/you/amunty.git
cd amunty
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:7000` after the containers are healthy.  
The admin password is auto-generated and printed in the logs:

```bash
docker compose logs amunty | grep "Admin password"
```

## Features (MVP)

- **Chat** — Multi-turn conversations with streaming responses, markdown rendering, code highlighting
- **Model Gateway** — Connect Ollama, vLLM, llama.cpp, OpenAI, OpenRouter — all via a unified settings UI
- **Memory** — Persistent vector memory (ChromaDB) — the AI learns about you over time
- **Tools** — Web search, URL reading, file operations — extensible via tool manifests
- **Local-first** — All data stays on disk. SQLite + ChromaDB. No cloud dependencies.

## Architecture

```
Browser (React PWA)
    ↕ HTTP / SSE
FastAPI Gateway
    ↕
┌─────────────┬──────────────┬─────────────┐
│ chat_engine │ tool_executor│ memory_store │
│             │              │              │
│ model_gateway              │  ChromaDB    │
│ (Ollama/OpenAI/vLLM)       │  (fastembed) │
└─────────────┴──────────────┴─────────────┘
    ↕
SQLite (WAL mode)
```

## Configuration

All settings are manageable from the browser Settings panel. Only touch `.env` for deployment-level overrides.

## License

MIT
