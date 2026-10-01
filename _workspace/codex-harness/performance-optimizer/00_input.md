# Agent Crossing long-running slowdown diagnosis

## User request

Analyze what made the computer slow after Agent Crossing had been running for a long time. Inspect the database, logs, processes, containers, memory, CPU, I/O, and relevant code paths.

## Scope

- Diagnosis only; do not delete data, restart services, or change configuration/code.
- Primary target: `local-agent-crossing-backend` and `agent-crossing-postgres`.
- Compare Agent Crossing resource use with other running containers so attribution is evidence-based.
- The backend was explicitly stopped immediately before this analysis; historical evidence must come from logs, database state, container metadata, and code.

## Known observations before analysis

- `local-agent-crossing-backend` had been up for about four days and was unhealthy.
- Automatic save failed with PostgreSQL `ProgramLimitExceeded`: JSONB array elements exceeded 268435455 bytes.
- The failed in-memory snapshot was logged as approximately 795 MB at turn 29900.
- The latest successful persisted active session was save version 215, turn 10700, with a serialized snapshot around 295 MB.
- The backend container is now stopped; frontend and PostgreSQL remain running.

## Deliverable

Rank root causes by confidence and likely impact. Separate direct evidence, inference, and unknowns. Include safe remediation recommendations, but do not apply them.
