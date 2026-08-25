# Deploy guide

1. Start the local PostgreSQL service with `docker compose up -d postgres`.
2. Apply schema migrations with `pnpm db:migrate`.
3. Start or restart the FastAPI and frontend services.
4. Verify `/sessions`, `/world/state`, and a `/ws/world` snapshot.

For non-local deployment, override PostgreSQL credentials, avoid public port publishing, and protect session mutation endpoints at the reverse-proxy boundary.

