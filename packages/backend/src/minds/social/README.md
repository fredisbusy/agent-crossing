# minds/social

두 마음(`ScheduleMind`, `LLMMind`)이 함께 쓰는 사회 상태 (SPEC §12, §13). 마음은 "무엇을 할지·말할지"만 따로 정한다.

- 진입점: `SocialState`, `SocialSeed`, `Agenda`, `intent_for_slot` (`__init__.py`)
- `agenda.py` 평소 일과(`Routine`) 위에 행사 약속(주최·손님)을 덮어쓰고 행동 의도로 바꾼다
- `state.py` 화행 효과(수락 → 약속, 초대·소문 → 사실, 선물 → 우호도)와 꺼낼 이야깃거리(`talking_points`)
- `facts.py` 사실 저장소(행사 소문 포함), `friendship.py` 우호도·쿨다운·오랜만 판정
- `events.py` 행사·시각·장소 문장 표현, `conversation.py` 대화를 멈추는 공통 조건
- 일과 출처만 마음마다 다르다: 규칙 마음은 일정표, LLM 마음은 하루 계획
- 의존 방향: `world.contracts`만 import한다
