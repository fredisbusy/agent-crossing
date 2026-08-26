# DB 스키마

`agent_roster(agent_id PK, enabled, created_at, updated_at)`. 시작 시 신규 persona만 기본
활성으로 추가하고 기존 선택은 덮어쓰지 않는다. Alembic revision은 `0007`이다.
