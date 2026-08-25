# Input

- **날짜**: 2026-08-25
- **트리거**: `.claude/` 하네스의 도메인 분할(backend-brain / backend-api /
  frontend-dev / db-prisma)을 기준으로 코드베이스를 직접 읽고, 실제 구현이
  `SPEC.md`/`AGENTS.md`와 얼마나 일치하는지 검증해 달라는 요청.
- **목적**: 현재 구현 상태를 file:line 근거와 함께 정리하고, 손볼 지점을
  교차 발견사항 우선순위로 제시.
- **관련 문서**: `SPEC.md`, `AGENTS.md` §9(Brain/Governance/Diagnostics 경계),
  `TODO.md` §2-D.

## 산출물

- `02_design.md` — 분석 본문 (인지 루프 / Backend / Frontend / DB / 교차 발견사항)
