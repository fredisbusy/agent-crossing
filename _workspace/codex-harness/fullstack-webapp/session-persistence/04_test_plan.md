# Test plan

- Prisma schema validation and migration deployment.
- Repository create/list/save/load with PostgreSQL.
- Runtime snapshot round trip for memory, plans, dialogue, movement, counters, cooldown, and logs.
- API happy paths plus stale-version, malformed ID, missing session, and unavailable DB.
- Frontend parser/component behavior and responsive production build.
- Live OrbStack flow: create -> advance -> save -> create another -> load -> verify restored clock/turn/session.

