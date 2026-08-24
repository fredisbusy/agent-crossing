# Resident selection bridge

## 2026-08-24

- React resident buttons dispatch `selectAgent(agentId)` to the shared Zustand game store.
- `followRequestId` increments for every dispatch so selecting the same resident can re-center the camera after a manual drag.
- `MainScene` subscribes to the store and routes each request to its existing `followAgent()` behavior.
- Agent IDs are matched case-insensitively because backend snapshots use lowercase IDs while Tiled spawn IDs are title-cased.

## Mock-only UI remediation — 2026-08-24

- The observer derives its featured activity from authoritative active-minute timestamps instead of a fabricated diffusion counter.
- Zustand owns scene context, selection commands, and semantic interactable feedback between React and Phaser.
- Both Phaser scenes consume resident selection; InteriorScene redraws occupants from every accepted snapshot.
- MainScene owns pan, wheel, pinch, semantic object hit zones, and outdoor follow behavior.

## Cognitive observability dashboard — 2026-08-24

- `WorldRuntime` records completed automatic and manual cognitive turns in a
  thread-safe bounded `DashboardEventBuffer` owned by the diagnostics layer.
- `GET /dashboard/state` joins spatial state, live plan hierarchy, memory stream,
  reflection progress, and recent diagnostics without extending `ActionLoopResult`.
- `main.tsx` lazy-loads either the Phaser game or dashboard based on pathname, so
  visiting `/dashboard` does not boot or download the Phaser runtime chunk.
- The dashboard uses a dedicated polling hook and strict runtime parser rather than
  overloading the Phaser/Zustand game bridge.

## Directional relationship summaries — 2026-08-24

- A diagnostics helper derives each subject-to-target summary only from the subject's
  identity stable set and memory stream.
- The dashboard joins that directional evidence with the target's existing live status;
  no relationship state is added to the Brain result object.
