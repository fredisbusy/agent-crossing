# Review report

## Result

Passed. The deployment now separates the Agent Crossing backend from the service on port 8000.

## Evidence

- Backend tests: 114 passed, 10 skipped.
- Frontend build: passed; existing large-chunk warning only.
- Backend LaunchAgent: running on `127.0.0.1:8001`.
- Local spatial state: HTTP 200 with a live Briar Cove snapshot.
- Caddy configuration: valid and reloaded successfully.
- Public WebSocket: HTTP 101 followed by incrementing world snapshots.

## Non-blocking observation

The cognitive runtime logged an Ollama TLS embedding connection error during startup. The spatial runtime recovered independently and serves the world stream as specified.

## 2026-08-24 lifecycle review scope

- Architecture: one planning coordinator owns day/hour/minute JIT state; spatial runtime consumes explicit active-minute locations.
- Safety: the romantic premise is asymmetric private knowledge, with explicit consent and boundary constraints.
- UI: the observer clock and resident activity now come from authoritative WebSocket state.
- Backend regression: 121 passed, 10 skipped.
- Recursive workspace build: passed; existing frontend large-chunk warning only.
- Live runtime: scheduler advanced from 06:00 through 09:15 while background qwen planning remained isolated from the clock.
- Live movement: Jiho arrived at Story House and Sujin moved from Sage Cottage toward The Honey Cup after the 08:00 plan transition.
- Runtime capacity: qwen authors day broad strokes in the background; deterministic hour/minute subdivision keeps the 27B model available for real encounters.
- Remaining scope: restart persistence and non-dialogue perceive/retrieve/reflect are tracked as incomplete TODO items; this is an accelerated daily-life MVP, not full paper parity.

## Readable bubble review scope

- Actual policy-approved replies cross the runtime-to-spatial WebSocket boundary as `speech`.
- User-facing thought summaries and active actions use `thought`/`action`; raw model thought and diagnostics remain private.
- Frontend owns punctuation: speech is plain, thought/action receive exactly one pair of parentheses.
- Regression: 124 backend tests passed, 10 live/optional tests skipped; frontend production build passed.
- Live contract: action overlays publish Korean text through `bubble_kind=action`; bridge tests prove policy-approved speech and public thought summaries replace it without leaking model thought or self-critique.

## 2026-08-24 resident card interaction review

- Root cause: resident rows were decorative `article` elements with no interaction handler; only Phaser sprites could call camera follow.
- Fix: native buttons now dispatch selection through Zustand to `MainScene`, with a request counter for same-agent re-centering.
- Accessibility: button names, pressed state, focus outline, and touch manipulation are present.
- Verification: frontend production build passed; the public site at a `390x844` viewport changed selection, closed the panel, and preserved selection after reopening.

## 2026-08-24 mock-only UI remediation review

- Removed fabricated Moonflower diffusion copy, `1 / 2`, and fixed 50% progress.
- Added truthful current/expired active-minute presentation and accurate resident status/destination fallbacks.
- Added scene-aware controls, live enlarged-interior residents, outdoor follow on interior selection, semantic interactable feedback, and pinch zoom.
- Added Vitest presentation/store contracts and connected root `pnpm test` to backend plus frontend suites.
- Verification: 124 backend tests passed, 10 skipped; 12 frontend tests passed; frontend production build and public 390x844 DOM verification passed with zero browser warnings/errors.

## 2026-08-24 cognitive observability dashboard review

- Added an isolated diagnostics event buffer without leaking trace fields into `/ws/world`.
- Added actual memory, reflection-progress, plan, state, dialogue, thought summary,
  self-critique, action summary, and governance-trace views at `/dashboard`.
- Full verification: 130 backend tests passed, 10 skipped; 14 frontend tests passed;
  recursive workspace build passed.
- Public verification: `/dashboard/state` returned HTTP 200 with live turn/revision data;
  browser showed LIVE status, two agents, actual memory rows and diagnostics, Sujin
  selection worked, and the browser console contained no errors.
- Known follow-up: event history and memories remain in-process and reset with the backend;
  public dashboard authentication is not yet implemented.

## 2026-08-24 directional relationship summary review

- Added subject-scoped, asymmetric relationship summaries with inspectable persona and
  memory evidence.
- Kept numeric affinity explicitly unmodeled instead of repurposing memory importance.
- Added perspective switching and target live-state context in both overview and Relationship views.
- Verification: 132 backend tests passed, 10 skipped; 16 frontend tests passed;
  recursive workspace build passed. The public state endpoint returned directional
  Jiho-to-Sujin and Sujin-to-Jiho summaries with `affinity_score: null`.

## 2026-08-26 review pending

The earlier `not_modeled` decision was superseded by explicit user approval. Review now
covers the v1 domain rules, snapshot/projection consistency, coordinated API/parser
break, master-detail screen, and live session save/load evidence.

## 2026-08-26 relationship-v1 result

- Targeted backend verification: 48 passed, 1 skipped; Ruff passed.
- Frontend verification: 20 tests passed; recursive workspace build passed.
- Alembic is at `0005 (head)` and autogenerate check is clean. A live save stored snapshot schema v4 with 30
  directional states and 6 events, matching 30 state and 6 event projection rows.
- Live API showed completed dialogue updates in both directions with stable UUID5 event
  IDs. Reload retained previous IDs while the resumed scheduler could append new events.
- Browser QA at desktop and 390px found 5 target controls, 5 score meters, no horizontal
  overflow, no console errors, and no exposed `planning_route`/`moving_to:` strings.
- Full backend suite had 222 passing tests, 11 skipped, and 5 unrelated failures in
  pre-existing dirty planning/settings changes; relationship-targeted tests pass.
- `affinity` and `romantic_interest` are independent. Friendly dialogue leaves romantic
  interest unchanged; only explicit romantic recognition, welcome, or boundary events
  modify it.

## 2026-08-26 dashboard tabs result

- Public state dropped from the earlier 280,413-byte sample to 117,828 bytes with
  `memory_limit=50&event_limit=0`; all six agents resolved a physical or arrival location.
- Public projection now preserves memory/reflection/relationship evidence text by user
  decision while exposing zero private event trace fields or embeddings.
- Targeted backend tests: 12 passed. Frontend: 27 passed across 6 files. Ruff and
  recursive workspace build passed.
- Public browser verification passed for tab URL state, ArrowRight navigation, original
  memory content, plan status, and diagnostics filters. The in-app browser lacked viewport
  resizing, so final physical-device mobile QA remains a deployment check.
- Final public browser verification showed all 45 Haeun reflections through the dedicated
  reflection cursor with no placeholder, login copy, alert, or console error.
- Full backend suite: 228 passed, 11 skipped, 5 unrelated failures in existing dirty
  planning/settings work; dashboard-targeted tests passed.
