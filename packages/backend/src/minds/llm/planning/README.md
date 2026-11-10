# minds/llm/planning

LLM 마음의 일과: 하루 계획을 지도 장소 구간으로 옮기고, 지금 시각만 시간 → 5~15분 단위로 쪼갠다 (SPEC §7, §12).

- 진입점: `PlannedRoutine`, `Decomposer`, `plan_request`, `resolve_place` (`__init__.py`)
- `routine.py` 하루 계획 → 구간(`Slot`)과 원래 `DayPlanItem` 짝, 계획이 빈 시간의 쉬기·잠, 지금 이후 구간 교체(`replace_from`)
- `decompose.py` just-in-time 분해. 시간 단위는 하루 계획 항목당 1회, 분 단위는 시간 항목당 1~2회(상한 3회)를 캐시한다. 실패도 캐시하고 하루 계획 구간으로 대체. `invalidate`로 캐시를 비운다
- `reaction.py` 관찰에 반응할지 판정하고 지금 이후만 재계획한다. `reaction_notes.py`는 그 결정을 plan 기억 문장으로 만든다
- 약속·쉬기·잠 구간은 분해하지 않는다. 분 단위 장소는 같은 건물 안일 때만 쓴다
- 의존 방향: `minds.social`, `world.contracts`, `agents.planning`(모델·선택 함수)
