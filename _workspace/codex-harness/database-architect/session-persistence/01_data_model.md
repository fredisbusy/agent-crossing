# Data model

```text
GameSession
 |- 1:N SessionCharacter
 |    |- 1:N SessionMemory
 |    |- 1:N SessionPlanItem
 |- 1:1 SessionDialogueState
 |- 1:N SessionCognitiveLog
```

`GameSession.snapshot` is a versioned JSONB recovery envelope. The child tables are the queryable, normalized projection written in the same transaction. Runtime-only tasks, sockets, locks, and Phaser state are never persisted.

Important constraints:

- UUID identifiers and bounded session names.
- Optimistic `saveVersion` on overwrites.
- Unique character identity per session.
- Unique memory local ID per character, with 1-10 importance and vector(1024).
- Unique plan ordinal per character and level.
- Unique cognitive-log sequence per session.
- Cascade deletion from session to its private state.

