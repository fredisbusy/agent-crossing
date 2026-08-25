---
name: db-prisma
description: Use for packages/database work — Prisma schema changes, migrations, and their downstream impact on packages/backend (pgvector/PostgreSQL) and packages/shared types.
tools: Read, Edit, Write, Bash, Grep, Glob
---

You work on `packages/database/prisma/` (schema.prisma, migrations) — the
PostgreSQL + pgvector store shared by the backend memory system.

## Rules

- 스키마 변경은 항상 마이그레이션으로 남긴다. 수동으로 DB를 건드리지 않는다.
- `pnpm db:validate` (`pnpm --filter @agent-crossing/database build`)로 스키마를
  검증한 뒤 `pnpm db:migrate`를 실행한다. 상태 확인은 `pnpm db:status`.
- pgvector 관련 컬럼/인덱스 변경은 `packages/backend/src/agents/memory/`의
  retrieval 코드와 `SPEC.md`의 retrieval 정의에 영향을 주는지 먼저 확인한다.
- 스키마와 `packages/shared`의 타입이 어긋나지 않도록 함께 갱신한다.

## Verification

`pnpm db:validate` → `pnpm db:migrate` → `pnpm db:status`. 마이그레이션이
backend 코드에 영향을 준다면 `uv run pytest packages/backend/tests`도 실행한다.
