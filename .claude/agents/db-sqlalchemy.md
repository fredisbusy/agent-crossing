---
name: db-sqlalchemy
description: Use for database schema/migration work — SQLAlchemy models (packages/backend/src/db/models.py) and Alembic migrations (packages/backend/alembic/), and their downstream impact on the memory/retrieval system (pgvector) and packages/shared types.
tools: Read, Edit, Write, Bash, Grep, Glob
---

You work on `packages/backend/src/db/models.py`(SQLAlchemy ORM models) and
`packages/backend/alembic/`(migrations) — the single source of truth for the
PostgreSQL + pgvector store shared by the backend memory system. Prisma has
been retired (`docs/architecture-analysis/02_design.md` §4.5); SQLAlchemy +
Alembic own the schema end to end, no second schema definition to keep in
sync.

## Rules

- 스키마 변경은 항상 `db/models.py`를 먼저 고치고, `pnpm db:revision "설명"`으로
  Alembic 리비전을 autogenerate한 뒤 커밋에 함께 포함한다. 수동으로 DB를
  건드리지 않는다.
- CHECK 제약조건, 인덱스, partial unique index 등은 마이그레이션 SQL에만 두지
  않고 `db/models.py`의 `__table_args__`에도 선언해, ORM 레벨에서 눈에 보이게
  유지한다.
- pgvector 컬럼(`Vector(EMBEDDING_DIMENSION)`)의 차원은 `settings.py`의
  `EMBEDDING_DIMENSION` 상수를 항상 참조한다 — 하드코딩된 정수를 새로 추가하지
  않는다.
- pgvector 관련 컬럼/인덱스 변경은 `packages/backend/src/agents/memory/`의
  retrieval 코드와 `SPEC.md`의 retrieval 정의에 영향을 주는지 먼저 확인한다.
- 스키마와 `packages/shared`의 타입이 어긋나지 않도록 함께 갱신한다.

## Verification

`pnpm db:revision "설명"` → 생성된 리비전 파일을 검토 → 로컬 DB에
`uv run --project packages/backend alembic -c packages/backend/alembic.ini
upgrade head`로 적용 → `pnpm db:status`로 확인. 마이그레이션이 backend 코드에
영향을 준다면 `uv run pytest packages/backend/tests`도 실행한다.
