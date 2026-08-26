# Deployment change

1. Run `@agent-crossing/backend` on `127.0.0.1:8001` with a user LaunchAgent.
2. Route exact path `/ws/world` through Caddy to `127.0.0.1:8001`.
3. Keep the frontend reverse proxy on `127.0.0.1:3010`.
4. On HTTPS, derive `wss://<public-host>/ws/world` before applying the Vite dev fallback.
5. Verify port ownership, HTTP backend health, WebSocket upgrade, and the public page.

## Day lifecycle runtime

1. Backend startup creates the cognitive runtime with the existing spatial runtime.
2. The scheduler starts automatically at 06:00 and advances five game minutes per configured tick.
3. The spatial stream remains independent so movement/UI continue to publish while an LLM call is running.
4. Restart `com.fredly.agent-crossing-backend` after deployment and verify `/world/state` plus `/world/spatial/state`.

# 2026-08-24 mock-only UI remediation

No deployment configuration change is required. The existing Vite development service reflects frontend changes immediately; production deployment uses the normal frontend build artifact.

## 2026-08-24 cognitive observability dashboard

- The existing bind-mounted Vite and reload-enabled FastAPI containers reflect source changes.
- Vite proxies `/dashboard/state` and `/dashboard/events` to `backend:8001` inside the
  Docker network and to `127.0.0.1:8001` for host-local development.
- Caddy continues to proxy the frontend origin; no new public host is required.
- Verify `https://agentcrossing.byfred.io/dashboard` and `/dashboard/state` after changes.

## 2026-08-24 directional relationship summaries

No deployment configuration change is required. The existing dashboard state endpoint
and frontend bundle carry the additive relationship contract.

## 2026-08-26 rollout

Apply Alembic revision `0004` before the updated backend writes projections. Deploy the
backend/shared/frontend as one coordinated contract change, then save/reload a session
and compare relationship revisions and event IDs before and after restore.

## 2026-08-26 dashboard tabs rollout

- Deploy backend/shared/frontend as one additive contract change; no migration is needed.
- The Vite dev proxy must route `/dashboard/agents` in addition to state/events.
- Verify public state with `memory_limit=50&event_limit=0`, then verify the six tabs,
  URL persistence, keyboard navigation, freshness status, and mobile layout.
- No login gate is required. Verify memory/reflection/relationship text is visible while
  provider secrets, embeddings, and internal diagnostic traces remain absent.
