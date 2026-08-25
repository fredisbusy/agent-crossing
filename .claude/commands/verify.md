---
description: Run this project's standard verification suite (AGENTS.md §6)
---

Run the verification steps appropriate to what changed, per AGENTS.md §6:

1. If `packages/backend` changed: `pnpm test:backend` (or narrow with
   `uv run pytest -c packages/backend/pyproject.toml <path>`).
2. If `packages/shared` or `packages/frontend` changed:
   `pnpm --filter @agent-crossing/shared build` and/or
   `pnpm --filter @agent-crossing/frontend build`.
3. If `packages/database` changed: `pnpm db:validate` then `pnpm db:status`.
4. For a broad change, `pnpm -r build` and `pnpm test`.

After running, report pass/fail per step. On failure, fix and re-run rather
than reporting a partial pass. Update the relevant `TODO.md` item status if
this completes or advances a tracked task.
