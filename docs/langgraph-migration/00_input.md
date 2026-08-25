# Input

- **날짜**: 스파이크 시작 시점(브랜치 `spike/langgraph-feasibility`).
- **트리거**: 기존 백엔드 개념(reaction/reflection/planning/brain 루프) 중
  어떤 것을 LangGraph의 state/node/edge/subgraph로 재구성할 수 있는지 조사.
- **제약**: world/runtime 권위와 커스텀 메모리 스코어링은 마이그레이션 대상에서
  제외하고 현재 백엔드에 그대로 둔다. 첫 단계는 작고, 되돌릴 수 있고, 동작을
  보존해야 한다.

## 현재 상태 (2026-08-25)

**완료로 대체됨.** 제안된 마이그레이션은 끝났고, reaction/reflection/planning/
brain 루프 모두 LangGraph `StateGraph` 러너로 구현되었다. 이 폴더는 원래
계획의 기록으로만 남긴다. 현재 아키텍처는 `docs/architecture-analysis/02_design.md`
§1을 참고할 것.

## 산출물

- `02_design.md` — 마이그레이션 후보 테이블과 진행 순서(원안 + 실제 결과)
