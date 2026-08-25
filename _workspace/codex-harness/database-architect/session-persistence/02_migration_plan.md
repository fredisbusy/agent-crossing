# Migration plan

1. Keep the existing `vector_memories` table for compatibility and enable `vector` idempotently.
2. Apply the checked-in Prisma migration to create session tables, checks, foreign keys, and access-path indexes.
3. Stop using SQLAlchemy `Base.metadata.create_all()`; application startup only verifies connectivity and the Prisma migration contract.
4. Use `prisma migrate deploy` for OrbStack and deployments.
5. Rollback is a deliberate, data-destructive drop of session tables only; the legacy vector table and volume remain intact.

