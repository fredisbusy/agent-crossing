# minds/llm

논문 인지 루프로 움직이는 마음 `LLMMind` (SPEC §3~§7, §12). `ScheduleMind`와 같은 `Mind` 프로토콜을 따른다.

- 진입점: `LLMMind`, `LlmPersona`, `ManagedMemory` (`__init__.py`)
- `mind.py` 하루 계획 → 행동, 조우 판단, 대화(문장 + 화행 구조화 출력), 관찰 → 기억·성찰
- `routine.py` 하루 계획을 지도 장소 구간(`Routine`)으로, `memory.py` `MemoryManager` 어댑터
- `prompts.py` 대화·조우 프롬프트, `parsing.py` 응답 → 화행(실패 시 smalltalk)
- 약속·소문·우호도·선물·대화 멈춤은 `minds.social`을 규칙 마음과 함께 쓴다(따로 구현하지 않는다)
- 의존 방향: `minds.social`, `world.contracts`, `agents`(기억·계획·성찰 부품), `llm`
