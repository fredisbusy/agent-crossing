# minds/schedule

스타듀밸리·동물의 숲식 규칙 NPC 마음 `ScheduleMind` (SPEC §12, §13). LLM 호출 0.

- 진입점: `build_schedule_mind`, `load_archetype`, `ScheduleConfig` (`__init__.py`)
- `timetable.py` 일정 선택·초대 덮어쓰기, `friendship.py` 우호도·쿨다운, `facts.py` 사실 저장소
- `rules.py` 화행 응답 규칙, `lines.py` 한국어 대사 템플릿(메타 단어 금지)
- 원형 JSON은 `packages/backend/residents/archetypes/`, 자리표시자 `{home}`·`{bedroom}`
- 의존 방향: `world.contracts`만 import한다. 난수·시계는 주입(`random.Random`, `ctx.now`).
