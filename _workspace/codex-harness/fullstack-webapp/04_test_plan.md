# Verification plan

- Backend regression: `pnpm test:backend`.
- Frontend type/build: `pnpm --filter @agent-crossing/frontend build`.
- Runtime ownership: confirm `8000` remains owned by OrbStack and Uvicorn owns `127.0.0.1:8001`.
- Local API: confirm `/world/spatial/state` returns HTTP 200.
- Public WebSocket: confirm HTTPS endpoint returns `101 Switching Protocols` and streams snapshots.
- Persistence: confirm the backend LaunchAgent is running and the Caddy configuration validates.

## Two-agent day lifecycle

- Unit-test half-open active-plan selection and JIT cache behavior.
- Verify Jiho-only crush knowledge and Sujin autonomy in persona fixtures.
- Build shared and frontend contracts after exposing game time and hierarchical plans.
- Run the full backend suite and recursive package build.
- Restart the live backend and observe automatic clock advancement and canonical destinations.

## Readable resident bubbles

- Verify spatial overlays default to action text and accept non-empty speech/thought.
- Verify blank cognitive overlays fall back to action text.
- Build shared/frontend contracts and inspect the live WebSocket payload.
- Confirm outdoor, home, and expanded interior views share the same parentheses rule.

## Resident card interaction

- Build: `pnpm --filter @agent-crossing/frontend build`.
- Mobile viewport (`390x844`): Jiho and Sujin rows are named buttons with `aria-pressed` state.
- Tap Sujin: selection changes and the observer panel closes.
- Reopen panel: Sujin remains selected; tap Jiho and verify the same behavior.
- Repeat-select the same resident after dragging to verify the camera re-centers.

## Mock-only UI remediation

- Run `pnpm test` so backend pytest and frontend Vitest both execute.
- Run `pnpm --filter @agent-crossing/frontend build` and recursive workspace build.
- Verify event title/progress derives from the selected resident and expired plans show synchronization state.
- Verify mobile hints use pinch/tap language and resident selection still closes the panel.
- Verify InteriorScene redraws residents on store snapshots and returns to outdoor follow on selection.
- Verify board/fountain/bench taps expose canonical resident-affordance feedback.

## Cognitive observability dashboard

- Unit-test bounded event retention, sequence cursor behavior, and structured fields.
- Unit-test strict dashboard payload parsing and malformed-memory rejection.
- Run full backend/frontend tests and recursive workspace build.
- Verify the public state endpoint returns current runtime facts.
- In a browser, select Sujin, open Memory and Diagnostics tabs, confirm real rows render,
  and confirm there are no browser console errors.
