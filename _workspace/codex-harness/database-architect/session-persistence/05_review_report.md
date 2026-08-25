# Final database review

- Prisma schema and migration are the DDL source of truth; SQLAlchemy is the typed Python runtime adapter.
- The migration is applied to the OrbStack PostgreSQL instance and preserves the existing `vector_memories` table.
- Session projections normalize characters, memories/citations, plans, dialogue state, and cognitive logs while retaining a versioned JSON snapshot for atomic restore.
- PostgreSQL is bound to loopback, diagnostics are sanitized, and save updates use optimistic version checks.
- Repository integration tests cover projection counts, round-trip restore, conflict rejection, cleanup, and prior-active-session restoration.

