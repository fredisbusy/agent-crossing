# Architecture

```text
React session menu
  -> same-origin /sessions API
  -> FastAPI lifecycle coordinator
       -> quiesce scheduler and spatial stream
       -> versioned runtime snapshot
       -> SQLAlchemy repository transaction
  -> PostgreSQL 16 / pgvector
       schema authority: Prisma Migrate
```

Loading builds and validates a detached runtime, then swaps the existing spatial stream to the restored runtime so connected WebSocket observers receive the new world without reconnecting.

