# Agent Crossing — Claude 작업 지침

이 문서는 포인터입니다. 실제 운영 규칙의 단일 소스는 아래 문서들입니다:

- [AGENTS.md](../AGENTS.md) — 모듈 경계, 코딩 규칙, Brain/Governance 경계, 검증/커밋 규칙 (최우선)
- [SPEC.md](../SPEC.md) — retrieval/reflect/plan 공식, 상수, 임계값의 단일 기준
- [TODO.md](../TODO.md) — 현재 작업 상태

충돌 시 SPEC.md, TODO.md가 AGENTS.md보다 우선합니다 (AGENTS.md §0).

## 이 레포에서 Claude를 쓸 때

- 작업 시작 전 TODO.md 관련 항목을 확인한다.
- `packages/backend/src/agents/brain/`을 건드릴 때는 `.claude/agents/backend-brain.md`의
  governance/diagnostics 분리 규칙을 따른다.
- 완료 후 최소 1회 검증: `.claude/commands/verify.md` 참고.
- `_workspace/codex-harness/`는 과거 Codex 세션의 role-pipeline 산출물 아카이브입니다.
  같은 역할이 필요하면 `.claude/agents/`의 서브에이전트를 사용하세요.
