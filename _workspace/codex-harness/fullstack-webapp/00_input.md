# Agent Crossing WebSocket port fix

- Scope: resolve the local port 8000 collision and restore the public HTTPS WebSocket.
- Frontend: Vite/React served through Caddy on `agentcrossing.byfred.io`.
- Backend: FastAPI/Uvicorn bound to loopback port `8001`.
- Proxy: route `/ws/world` to the backend and all other traffic to Vite on `3010`.
- Constraints: preserve the existing live-development frontend and avoid unrelated changes.

## 2026-08-24 two-agent day lifecycle

- Make Jiho and Sujin live an accelerated in-game day using day/hour/minute plans.
- Connect active plans to canonical Briar Cove movement, encounters, and the observer UI.
- Persona premise: Jiho privately likes Sujin; Sujin knows him as a friend and retains independent goals and boundaries.
- Generation model: `ollama_chat/qwen3.8:27b-mlx`; embedding model: `bge-m3:latest`.

## 2026-08-24 resident card interaction fix

- Symptom: tapping the Jiho Park or Sujin Lee rows in the mobile observer panel has no effect.
- Expected behavior: selecting a resident follows that NPC with the existing Phaser camera behavior.
- Mobile acceptance: close the observer panel after selection so the followed resident is visible immediately.
- Constraint: keep React-to-Phaser state sharing in the Zustand bridge and do not implement the unfinished memory/plan/reflection inspector.
