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

## 2026-08-24 resident card interaction review

- Root cause: resident rows were decorative `article` elements with no interaction handler; only Phaser sprites could call camera follow.
- Fix: native buttons now dispatch selection through Zustand to `MainScene`, with a request counter for same-agent re-centering.
- Accessibility: button names, pressed state, focus outline, and touch manipulation are present.
- Verification: frontend production build passed; the public site at a `390x844` viewport changed selection, closed the panel, and preserved selection after reopening.
