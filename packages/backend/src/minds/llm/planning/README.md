# minds/llm/planning

LLM 마음의 일과: 하루 계획을 지도 장소 구간으로 옮긴다 (SPEC §7, §12).

- 진입점: `PlannedRoutine`, `plan_request`, `resolve_place` (`__init__.py`)
- `routine.py` 하루 계획 → 구간(`Slot`), 계획이 빈 시간의 쉬기·잠
- 의존 방향: `minds.social`, `world.contracts`, `agents.planning.models`
