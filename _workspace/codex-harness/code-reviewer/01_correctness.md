# Correctness findings

## High

1. The seed-event panel is hard-coded: event text, `1 / 2`, and 50% progress never consume runtime state.
2. Resident follow requests and the persistent `CLICK NPC` hint are dead while `InteriorScene` is active because only `MainScene` owns the follow subscription and handlers.
3. Enlarged-interior residents are drawn from a one-time store snapshot and remain stale until the scene is reopened.

## Medium

1. The notice board, fountain, and bench come from the semantic `interactables` layer but only render graphics and expose no user interaction.
2. Resident status and destination fallbacks can claim `활동 중` and `마을 광장` when the agent is idle, blocked, or has no destination.
3. Mobile still advertises wheel zoom, but no pinch gesture path exists.
