# API impact

## 2026-08-24 mock-only UI remediation

No API endpoint or WebSocket schema was added. The UI derives truthful presentation from the existing authoritative spatial snapshot. Missing rolling-deploy bubble fields receive a frontend compatibility fallback.

## 2026-08-24 cognitive observability dashboard

- `GET /dashboard/state?memory_limit=100&event_limit=100`
  returns world health, agents, recent memories, active/full plans, reflection progress,
  recent cognitive events, and the latest monotonic sequence.
- `GET /dashboard/events?after=<sequence>&limit=100` returns cursor-filtered events.
- Diagnostics responses omit embedding, provider `raw_response`, prompt, and API key.
- `/ws/world` remains unchanged and continues to carry only public spatial snapshots.
