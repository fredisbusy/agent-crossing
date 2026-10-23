# api

마을 시뮬레이션 HTTP/WebSocket 경계 (SPEC §15). 백엔드가 단일 권한이고 프런트는 스냅샷을 받는다.

- 진입점: `main.create_app()`, `main.app`. 응답 스키마는 `schemas.py`, 공유 DTO는 `world.contracts`.
- 엔드포인트: `GET /`, `GET /world/state`, `GET /world/text`(QA 훅), `POST /world/advance?minutes=N`(1..1440), `POST /world/tick/start|stop`, `WS /ws/world`.
- WS 메시지: `{"type":"snapshot","snapshot": WorldSnapshot}`. 접속 즉시 1회, 이후 틱마다.
- 설정: `TOWN_SCENARIO`, `TOWN_AGENTS`, `TOWN_AGENT_COUNT`(기본 0 = LLM 없음), `TOWN_SEED`, `WORLD_TICK_INTERVAL_SECONDS`.
- 의존 방향: `world.scenarios`(조립), `world.town.TownRuntime`. 시뮬레이션 로직은 여기 두지 않는다.
