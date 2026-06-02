<p align="center">
  <img src="https://github.com/user-attachments/assets/856899a4-f2e2-4174-88fe-5587b3201b8d" alt="Amunty Logo">
</p>

# Amunty

Amunty is a self-hosted, local-first AI workspace. Think of it as your own personal ChatGPT that runs entirely on your hardware, keeping your data private and secure on your disk.

## Features

- **Chat** — Multi-turn conversations with streaming responses, markdown rendering, and code highlighting.
- **Model Gateway** — Connect to Ollama, vLLM, llama.cpp, OpenAI, OpenRouter, and more via a unified settings UI.
- **Memory** — Persistent vector memory (ChromaDB) allows the AI to learn about you over time.
- **Tools** — Extensible tools for web search, URL reading, file operations, and more via tool manifests.
- **Local-first** — All data stays on disk using SQLite and ChromaDB. No cloud dependencies.

## Quick Start

Get Amunty running in minutes:

```bash
git clone https://github.com/Femfus/amunty.git
cd amunty
cp .env.example .env
docker compose up -d --build
