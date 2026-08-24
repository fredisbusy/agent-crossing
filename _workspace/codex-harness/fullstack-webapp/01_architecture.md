# Resident selection bridge

## 2026-08-24

- React resident buttons dispatch `selectAgent(agentId)` to the shared Zustand game store.
- `followRequestId` increments for every dispatch so selecting the same resident can re-center the camera after a manual drag.
- `MainScene` subscribes to the store and routes each request to its existing `followAgent()` behavior.
- Agent IDs are matched case-insensitively because backend snapshots use lowercase IDs while Tiled spawn IDs are title-cased.
