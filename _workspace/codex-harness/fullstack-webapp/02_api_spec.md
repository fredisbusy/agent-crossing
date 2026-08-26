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

## 2026-08-24 directional relationship summaries

- Every dashboard agent includes `relationships`, omitting self-relations.
- Each entry includes target identity, qualitative summary, supporting persona/memory
  evidence, `affinity_score: null`, and `measurement: "not_modeled"`.
- `/ws/world` remains unchanged.

## 2026-08-26 coordinated contract replacement

- `measurement` is `modeled_v1`.
- Every directional item carries five bounded metrics, revision/timestamps, up to five
  recent events with applied deltas, plus the existing safe qualitative evidence.
- `affinity` is interpersonal liking; `romantic_interest` is independently modeled
  romantic intent. Ordinary friendly interaction does not raise romantic interest.
- Dashboard agents expose authoritative `current_location_path` separately from destination.

## 2026-08-26 public dashboard projection

- `GET /dashboard/state` adds `snapshot_generated_at`, `oldest_sequence`, location
  source, reflection totals/timestamps, memory totals/has-more, and last replan reason.
- Public memories contain original content without embeddings; relationship qualitative
  summary/evidence is included. Public events retain an explicit safe-field allowlist.
- `GET /dashboard/agents/{agent_id}/memories` supports stable `before_id`, `limit`,
  `node_type`, and `min_importance` cursor queries with original content.
- `/dashboard/events?after=` is consumed independently from state polling.
