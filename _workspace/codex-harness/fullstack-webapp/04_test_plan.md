# Verification plan

- Backend regression: `pnpm test:backend`.
- Frontend type/build: `pnpm --filter @agent-crossing/frontend build`.
- Runtime ownership: confirm `8000` remains owned by OrbStack and Uvicorn owns `127.0.0.1:8001`.
- Local API: confirm `/world/spatial/state` returns HTTP 200.
- Public WebSocket: confirm HTTPS endpoint returns `101 Switching Protocols` and streams snapshots.
- Persistence: confirm the backend LaunchAgent is running and the Caddy configuration validates.
