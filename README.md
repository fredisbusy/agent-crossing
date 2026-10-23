# Agent Crossing

Autonomous social simulation inspired by **Generative Agents (Park et al., 2023)**.
Built with **React 19 + Phaser 3** (frontend) and **FastAPI** (backend).

## Status

> Work in progress. Core architecture is set, cognitive loop is under active implementation.

## What this project aims to do

- NPCs plan their day, remember experiences, and react to unexpected events.
- Memories are retrieved by recency/importance/relevance scoring.
- Reflection generates higher-level insights from recent experiences.
- Multiple agents interact, exchange information, and form social dynamics.

## Tech Stack

- Frontend: React 19, Phaser 3, Zustand, Vite
- Backend: FastAPI, Pydantic, uvicorn, uv
- AI/Memory: local LLM (MLX on Apple Silicon), PostgreSQL + pgvector, sentence-transformers
- Monorepo: pnpm workspace

## Project Structure

```text
packages/
  shared/      # shared types/constants
  frontend/    # React + Phaser client
  backend/     # FastAPI + town simulation
```

## Getting Started

### Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.11+
- uv

### Install

```bash
pnpm install
uv sync --project packages/backend
```

### Run (dev)

```bash
# terminal 1
pnpm dev:backend

# terminal 2
pnpm dev:frontend
```

The backend serves the town simulation (`TownSimulation`): `GET /world/state`, `GET /world/text`, `POST /world/advance?minutes=N`, `POST /world/tick/start|stop`, and `ws://localhost:8000/ws/world` for snapshots. By default every resident uses the rule-based mind (no LLM calls). Configure with `TOWN_SCENARIO`, `TOWN_AGENTS` (comma-separated resident ids), `TOWN_AGENT_COUNT`, `TOWN_SEED`.

Run a scenario headless and print its metrics:

```bash
pnpm dev:simulation -- --scenario valentine
```

### LLM provider switch

Backend runtime uses LiteLLM as the provider adapter. Switch model backends with `LLM_BACKEND`; each backend maps to the project-approved model names in `settings.py`.

```bash
# Fredly Ollama gateway
export LLM_BACKEND=ollama

# Google AI Studio
export LLM_BACKEND=google_ai_studio
export GOOGLE_AI_STUDIO_API_KEY=your_api_key
```

### PostgreSQL + pgvector (Docker)

```bash
docker compose up -d
```

Quick check:

```bash
docker compose exec postgres psql -U agent -d agent_crossing -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

If the result includes `vector`, pgvector is enabled.

### Tests

```bash
pnpm test:backend
# or
uv run --project packages/backend pytest -c packages/backend/pyproject.toml packages/backend/tests
```

## Roadmap

- See `TODO.md` for implementation checklist aligned with the paper.
- See `SPEC.md` for architecture and technical specification.

## Reference

- Paper: [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)

## License

TBD
