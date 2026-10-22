# world/scenarios

시나리오 씨앗과 하이브리드 평가 지표 (SPEC §16).

- 진입점: `load_scenario`, `apply_scenario`, `run_scenario`, `ScenarioReport` (`__init__.py`)
- 씨앗 JSON은 `packages/backend/residents/scenarios/<name>.json`: 시작 시각, 길이, 주민별 여는 행사·사실·우호도·시작 기억
- 씨앗은 주민 설정(`ResidentConfig`)에 더해지고, 마음 종류와 무관하게 `minds.social` 시작 상태가 된다
- `report.py`는 틱마다 행사를 아는·가기로 한·참석한 주민을 모은다(주최자 제외)
- 의존 방향: `world.residents`, `world.town`, `minds.social`
