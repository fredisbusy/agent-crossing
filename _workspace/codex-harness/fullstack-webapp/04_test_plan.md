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

## Resident card interaction

- Build: `pnpm --filter @agent-crossing/frontend build`.
- Mobile viewport (`390x844`): Jiho and Sujin rows are named buttons with `aria-pressed` state.
- Tap Sujin: selection changes and the observer panel closes.
- Reopen panel: Sujin remains selected; tap Jiho and verify the same behavior.
- Repeat-select the same resident after dragging to verify the camera re-centers.
