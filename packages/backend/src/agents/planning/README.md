# agents/planning

하루·시간·분 계획 생성 (SPEC §6).

- 진입점: `__init__.py` (`PlanningGraphRunner`, `Planner`, 계획 모델, `select_*`)
- `plan_prompts.py` -> `graph.py`(프롬프트, 생성, 파싱, 실패 시 재시도) -> `plan_parsing.py`/`json_utils.py`
- `models.py`: 계획 DTO. `selection.py`: 시각에 맞는 계획 항목 고르기
- 의존: `llm`(클라이언트 옵션, 템플릿)만 아래로 import한다.
