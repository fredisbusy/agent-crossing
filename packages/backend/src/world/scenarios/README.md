# world/scenarios

시나리오 씨앗과 하이브리드 평가 지표 (SPEC §16).

- 진입점: `build_town`(주민 설정 -> 마음 선택 -> 시나리오 -> 공간 -> 마음 공장 조립, CLI·API 공용), `load_scenario`, `apply_scenario`, `run_scenario`, `simulate`, `ScenarioReport` (`__init__.py`)
- 씨앗 JSON은 `packages/backend/residents/scenarios/<name>.json`: 시작 시각, 길이, 주민별 여는 행사·사실·우호도·시작 기억
- 씨앗은 주민 설정(`ResidentConfig`)에 더해지고, 마음 종류와 무관하게 `minds.social` 시작 상태가 된다
- `report.py`는 틱마다 행사를 아는·가기로 한·참석한 주민을 모은다(주최자 제외)
- 의존 방향: `world.residents`, `world.town`, `minds.social`
- 실측: `run_live_day.py`가 `build_town(llm_client=...)`에 호출 기록 클라이언트를 넣어 실제 LLM 호출 수·지연·형식 실패를 잰다.
