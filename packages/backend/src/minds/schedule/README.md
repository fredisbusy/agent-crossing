# minds/schedule

스타듀밸리·동물의 숲식 규칙 NPC 마음 `ScheduleMind` (SPEC §12, §13). LLM 호출 0.

- 진입점: `build_schedule_mind`, `load_archetype`, `ScheduleConfig` (`__init__.py`)
- `timetable.py` 원형 일정표 = 평소 일과(`Routine`). 약속 덮어쓰기는 `minds.social.Agenda`
- `rules.py` 무엇을 말할지 고르는 규칙(초대 수락, 소문 행사 참석, 먼저 초대·선물·소문), `lines.py` 존댓말·반말 공용 대사, `voices.py` 말투별 대사(메타 단어 금지)
- 약속·우호도·사실·화행 효과는 `minds.social.SocialState`를 LLM 마음과 함께 쓴다
- 원형 JSON은 `packages/backend/residents/archetypes/`, 자리표시자 `{home}`·`{bedroom}`
- 의존 방향: `minds.social`, `world.contracts`만 import한다. 난수·시계는 주입(`random.Random`, `ctx.now`).
