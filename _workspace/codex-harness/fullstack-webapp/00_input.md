# Agent Crossing WebSocket port fix

- Scope: resolve the local port 8000 collision and restore the public HTTPS WebSocket.
- Frontend: Vite/React served through Caddy on `agentcrossing.byfred.io`.
- Backend: FastAPI/Uvicorn bound to loopback port `8001`.
- Proxy: route `/ws/world` to the backend and all other traffic to Vite on `3010`.
- Constraints: preserve the existing live-development frontend and avoid unrelated changes.
