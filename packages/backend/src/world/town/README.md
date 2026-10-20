# world/town

마을 틱 루프 (SPEC §12, §14). 1틱 = 게임 시간 1분, `faithful` 모드만 지원한다.

- 책임: 시계(`clock.py`), 지각·관찰 문장(`perception.py`), 조우·쿨다운(`encounters.py`), 대화 상태(`conversation.py`), 틱 루프(`simulation.py`).
- 진입점: `TownSimulation`(`tick`, `run_minutes`, `snapshot`, `text_state`, `mind_calls`), `SimClock`, `TownConversation`.
- 틱 순서: 시계 진행 → 몸 이동 → 지각 → 마음 깨우기(행동 만료·즉시 깨움 사유) → 조우 → 대화.
- 시야·엿들은 말은 깨우지 않고 쌓아 두었다가 다음 깨움 때 전달한다(SPEC §14).
- 의존: `world.contracts`, `world.residents`. 공간·마음 구현은 주입받는다.
- 관찰 문장은 마음 종류와 무관한 한 형식이다.
